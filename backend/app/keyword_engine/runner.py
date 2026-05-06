"""サジェスト収集 → keyword_suggestions 保存のテナント別 runner。

Phase 1 では Google + Bing の2エンジン × ビルド済みシード を並列で取得し、
得られた派生語を keyword_suggestions に挿入する。

冪等性:
  - 同じ (tenant_id, source, seed_keyword, derived_keyword) の組が
    本日(JST)既に存在すれば挿入をスキップする。
  - これにより同日複数回ジョブを実行しても行が爆発しない。
"""

import asyncio
import uuid
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.keyword_suggestion import KeywordSuggestion
from app.db.models.tenant import Tenant
from app.keyword_engine.seed_builder import Seed, build_seeds
from app.keyword_engine.suggest_collector import (
    DEFAULT_TIMEOUT,
    fetch_bing_suggest,
    fetch_google_suggest,
)
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "collect_keyword_suggestions"

# シード間の最小待機(レート制限対策)。1秒1リクエスト相当。
INTER_SEED_DELAY_S = 1.0


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """指定テナントについてサジェストを収集し、挿入件数を返す。"""
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
        # SET LOCAL はパラメータバインドできないので文字列リテラルで埋める。
        # tenant_id は UUID で外部入力ではないため SQL injection の余地はない。
        await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        tenant = (
            await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
        ).one()
        seeds = build_seeds(tenant.business_context or {})
        if not seeds:
            log.info("seeds_empty", tenant_id=str(tenant_id))
            job_log.status = JobStatusEnum.success
            job_log.finished_at = datetime.now(UTC)
            await session.commit()
            return 0

        log.info(
            "suggest_collect_start",
            tenant_id=str(tenant_id),
            seed_count=len(seeds),
        )

        today = date.today()
        inserted = 0
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            for i, seed in enumerate(seeds):
                # Google + Bing を並列で1シード分取得
                g, b = await asyncio.gather(
                    fetch_google_suggest(seed.text, client=client),
                    fetch_bing_suggest(seed.text, client=client),
                )
                for result in (g, b):
                    inserted += await _persist(
                        session=session,
                        tenant_id=tenant_id,
                        seed=seed,
                        source=result.source,
                        derived_list=result.derived,
                        today=today,
                    )
                # 最後以外は緩衝
                if i < len(seeds) - 1:
                    await asyncio.sleep(INTER_SEED_DELAY_S)

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        await session.commit()
        log.info(
            "suggest_collect_done",
            tenant_id=str(tenant_id),
            inserted=inserted,
            seeds=len(seeds),
        )
        return inserted

    except Exception:
        await session.rollback()
        # 失敗ログを別トランザクションで保存
        log.exception("suggest_collect_failed", tenant_id=str(tenant_id))
        async with session.begin():
            failed = JobExecutionLog(
                tenant_id=tenant_id,
                job_name=JOB_NAME,
                status=JobStatusEnum.failed,
                started_at=started,
                finished_at=datetime.now(UTC),
            )
            session.add(failed)
        raise


async def _persist(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    seed: Seed,
    source: str,
    derived_list: tuple[str, ...],
    today: date,
) -> int:
    """同日同 (source, seed, derived) は skip。挿入数を返す。"""
    if not derived_list:
        return 0

    existing = set(
        (
            await session.scalars(
                select(KeywordSuggestion.derived_keyword).where(
                    KeywordSuggestion.tenant_id == tenant_id,
                    KeywordSuggestion.source == source,
                    KeywordSuggestion.seed_keyword == seed.text,
                    KeywordSuggestion.derived_keyword.in_(derived_list),
                    text("fetched_at::date = :today").bindparams(today=today),
                )
            )
        ).all()
    )

    inserted = 0
    for derived in derived_list:
        if derived in existing:
            continue
        session.add(
            KeywordSuggestion(
                tenant_id=tenant_id,
                source=source,
                seed_keyword=seed.text,
                derived_keyword=derived,
                raw_text=derived,
                metadata_json={"source_hint": seed.source_hint},
            )
        )
        inserted += 1

    if inserted:
        await session.flush()
    return inserted
