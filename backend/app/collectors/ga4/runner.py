"""GA4 収集ジョブのランナー。GSC ランナーと同じパターン。"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.ga4.client import Ga4Client
from app.collectors.google_oauth import (
    CredentialsNotFoundError,
    load_google_credentials,
)
from app.db.models.enums import CredentialProviderEnum, JobStatusEnum
from app.db.models.ga4_daily_metric import Ga4DailyMetric
from app.db.models.job_execution_log import JobExecutionLog
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "collect_ga4"


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    property_id: str,
    days: int = 7,
) -> int:
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
        creds = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.ga4)
        client = Ga4Client(creds, property_id=property_id)

        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days - 1)
        rows = await client.daily_metrics(start, end)

        await _upsert_metrics(session, tenant_id, rows)

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        job_log.job_metadata = {"row_count": len(rows), "start": start.isoformat(), "end": end.isoformat()}
        await session.commit()
        log.info("ga4_collect_done", tenant_id=str(tenant_id), rows=len(rows))
        return len(rows)

    except CredentialsNotFoundError as exc:
        job_log.status = JobStatusEnum.skipped
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = str(exc)
        await session.commit()
        log.warning("ga4_collect_skipped", tenant_id=str(tenant_id), reason=str(exc))
        return 0
    except Exception as exc:
        job_log.status = JobStatusEnum.failed
        job_log.finished_at = datetime.now(UTC)
        job_log.error_text = f"{type(exc).__name__}: {exc}"
        await session.commit()
        log.exception("ga4_collect_failed", tenant_id=str(tenant_id))
        raise


async def _upsert_metrics(session: AsyncSession, tenant_id: uuid.UUID, rows: list) -> None:
    if not rows:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "sessions": r.sessions,
            "users": r.users,
            "bounce_rate": r.bounce_rate,
            "conversions": r.conversions,
            "organic_sessions": r.organic_sessions,
        }
        for r in rows
    ]
    stmt = pg_insert(Ga4DailyMetric).values(payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ga4_daily_tenant_date",
        set_={
            "sessions": stmt.excluded.sessions,
            "users": stmt.excluded.users,
            "bounce_rate": stmt.excluded.bounce_rate,
            "conversions": stmt.excluded.conversions,
            "organic_sessions": stmt.excluded.organic_sessions,
        },
    )
    await session.execute(stmt)
