"""競合見出し収集 → keyword_suggestions 保存のテナント別 runner。

冪等性: 同日 (source, seed_keyword=null, derived_keyword) の重複は事前チェックで弾く。
seed_keyword は競合 URL を入れて「どのページから来たか」を残す。
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.competitor import Competitor
from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.keyword_suggestion import KeywordSuggestion
from app.keyword_engine.competitor_scraper import HeadingsResult, fetch_many
from app.keyword_engine.normalizer import normalize
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "collect_competitor_headings"


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """指定テナントについて競合見出しを取得 → keyword_suggestions に挿入。挿入件数を返す。"""
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
        await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        comps = list(
            (
                await session.scalars(
                    select(Competitor).where(
                        Competitor.tenant_id == tenant_id,
                        Competitor.is_active.is_(True),
                    )
                )
            ).all()
        )
        if not comps:
            log.info("competitors_empty", tenant_id=str(tenant_id))
            job_log.status = JobStatusEnum.success
            job_log.finished_at = datetime.now(UTC)
            await session.commit()
            return 0

        urls: list[str] = []
        for c in comps:
            if c.target_urls:
                urls.extend(u for u in c.target_urls if u)
            else:
                urls.append(f"https://{c.domain}/")

        log.info(
            "competitor_headings_start",
            tenant_id=str(tenant_id),
            url_count=len(urls),
            competitor_count=len(comps),
        )

        results = await fetch_many(urls, per_host_delay_s=5.0)
        today = date.today()
        inserted = 0
        for r in results:
            if r.error or r.skipped_robots:
                continue
            inserted += await _persist_one(
                session=session,
                tenant_id=tenant_id,
                result=r,
                today=today,
            )

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        await session.commit()
        log.info(
            "competitor_headings_done",
            tenant_id=str(tenant_id),
            inserted=inserted,
            urls=len(urls),
        )
        return inserted

    except Exception:
        await session.rollback()
        log.exception("competitor_headings_failed", tenant_id=str(tenant_id))
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


async def _persist_one(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    result: HeadingsResult,
    today: date,
) -> int:
    """1 URL 分の見出しを source 別に挿入。同日同 (source, derived) は skip。"""
    pairs: list[tuple[str, str, str]] = []  # (source, raw, normalized)
    if result.title:
        norm = normalize(result.title)
        if norm:
            pairs.append(("competitor_title", result.title, norm))
    for h in result.h1:
        norm = normalize(h)
        if norm:
            pairs.append(("competitor_h1", h, norm))
    for h in result.h2:
        norm = normalize(h)
        if norm:
            pairs.append(("competitor_h2", h, norm))
    for h in result.h3:
        norm = normalize(h)
        if norm:
            pairs.append(("competitor_h3", h, norm))

    if not pairs:
        return 0

    # 重複チェック: 同日同 (source, seed_keyword=URL, derived_keyword) の組
    derived_per_source: dict[str, list[str]] = {}
    for source, _, norm in pairs:
        derived_per_source.setdefault(source, []).append(norm)

    existing_keys: set[tuple[str, str]] = set()
    for source, derived_list in derived_per_source.items():
        rows = await session.execute(
            select(KeywordSuggestion.derived_keyword).where(
                KeywordSuggestion.tenant_id == tenant_id,
                KeywordSuggestion.source == source,
                KeywordSuggestion.seed_keyword == result.url,
                KeywordSuggestion.derived_keyword.in_(derived_list),
                text("fetched_at::date = :today").bindparams(today=today),
            )
        )
        for (d,) in rows:
            existing_keys.add((source, d))

    inserted = 0
    for source, raw, norm in pairs:
        if (source, norm) in existing_keys:
            continue
        session.add(
            KeywordSuggestion(
                tenant_id=tenant_id,
                source=source,
                seed_keyword=result.url,
                derived_keyword=norm,
                raw_text=raw,
                metadata_json={"source_url": result.url},
            )
        )
        inserted += 1

    if inserted:
        await session.flush()
    return inserted
