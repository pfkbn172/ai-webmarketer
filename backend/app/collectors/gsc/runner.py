"""GSC 収集ジョブのランナー。

スケジューラ(W3-01)が週次で run_for_tenant() を呼ぶ。
冪等性: (tenant_id, date, query_text) の UNIQUE 制約により、再実行しても重複しない
       (UPSERT で既存レコードを更新する)。
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.google_oauth import (
    CredentialsNotFoundError,
    load_google_credentials,
)
from app.collectors.gsc.client import GscClient
from app.db.models.enums import CredentialProviderEnum, JobStatusEnum
from app.db.models.gsc_query_metric import GscQueryMetric
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.tenant_credential import TenantCredential  # noqa: F401  (登録維持)
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "collect_gsc"


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    site_url: str,
    days: int = 7,
) -> int:
    """指定テナントの GSC データを過去 days 日間ぶん収集して DB に保存。

    Returns:
        保存(upsert)した行数
    """
    started = datetime.now(UTC)
    job_log = JobExecutionLog(
        tenant_id=tenant_id,
        job_name=JOB_NAME,
        status=JobStatusEnum.running,
        started_at=started,
    )
    session.add(job_log)
    await session.flush()

    try:
        repo = TenantCredentialRepository(session)
        creds = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.gsc)
        client = GscClient(creds, site_url=site_url)

        end = date.today() - timedelta(days=2)  # GSC は確定値の遅延 ~2 日
        start = end - timedelta(days=days - 1)
        rows = await client.query_metrics(
            start, end, dimensions=["date", "query"], row_limit=1000
        )

        await _upsert_metrics(session, tenant_id, rows)

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        job_log.job_metadata = {"row_count": len(rows), "start": start.isoformat(), "end": end.isoformat()}
        await session.commit()
        log.info("gsc_collect_done", tenant_id=str(tenant_id), rows=len(rows))
        return len(rows)

    except CredentialsNotFoundError as exc:
        job_log.status = JobStatusEnum.skipped
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = str(exc)
        await session.commit()
        log.warning("gsc_collect_skipped", tenant_id=str(tenant_id), reason=str(exc))
        return 0
    except Exception as exc:
        job_log.status = JobStatusEnum.failed
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = f"{type(exc).__name__}: {exc}"
        await session.commit()
        log.exception("gsc_collect_failed", tenant_id=str(tenant_id))
        raise


async def _upsert_metrics(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    rows: list,
) -> None:
    """GscQueryMetric への UPSERT(date, query_text 単位で再実行可能)。"""
    if not rows:
        return
    # RLS が効いているので、書き込み前に app.tenant_id がセットされている必要がある
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "query_text": r.query_text or "(unknown)",
            "clicks": r.clicks,
            "impressions": r.impressions,
            "ctr": r.ctr,
            "position": r.position,
        }
        for r in rows
    ]
    stmt = pg_insert(GscQueryMetric).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_gsc_qm_tenant_date_query",
        set_={
            "clicks": stmt.excluded.clicks,
            "impressions": stmt.excluded.impressions,
            "ctr": stmt.excluded.ctr,
            "position": stmt.excluded.position,
        },
    )
    await session.execute(stmt)
