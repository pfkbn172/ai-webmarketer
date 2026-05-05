"""PageSpeed Insights ランナー。

GSC で表示の多い TOP N URL を mobile/desktop 両方で計測し、page_speed_metrics に保存。
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.pagespeed.client import fetch
from app.db.models.enums import JobStatusEnum
from app.db.models.gsc_page_metric import GscPageMetric
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.page_speed_metric import PageSpeedMetric
from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "collect_pagespeed"


async def run_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    top_n: int = 5,
) -> int:
    api_key = settings.pagespeed_api_key
    if not api_key:
        log.warning("pagespeed_skip_no_api_key", tenant_id=str(tenant_id))
        return 0

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
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        # GSC で直近 30 日に表示が多かった URL TOP N
        end = date.today()
        start = end - timedelta(days=30)
        rows = (
            await session.execute(
                select(GscPageMetric.page)
                .where(
                    GscPageMetric.tenant_id == tenant_id,
                    GscPageMetric.date.between(start, end),
                )
                .group_by(GscPageMetric.page)
                .order_by(text("SUM(impressions) DESC"))
                .limit(top_n)
            )
        ).all()
        urls = [r.page for r in rows if r.page and r.page.startswith("http")]
        if not urls:
            log.info("pagespeed_no_urls", tenant_id=str(tenant_id))
            job_log.status = JobStatusEnum.skipped
            job_log.finished_at = datetime.now(UTC)
            await session.commit()
            return 0

        today = date.today()
        saved = 0
        for url in urls:
            for strategy in ("mobile", "desktop"):
                try:
                    res = await fetch(url, api_key=api_key, strategy=strategy)
                except Exception as exc:
                    log.warning("pagespeed_fetch_failed", url=url, strategy=strategy, err=str(exc))
                    continue
                stmt = pg_insert(PageSpeedMetric).values(
                    tenant_id=tenant_id,
                    date=today,
                    page_url=url,
                    strategy=strategy,
                    performance_score=res.performance_score,
                    lcp_ms=res.lcp_ms,
                    cls=res.cls,
                    inp_ms=res.inp_ms,
                    fcp_ms=res.fcp_ms,
                    ttfb_ms=res.ttfb_ms,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_psm_tenant_date_url_strategy",
                    set_={
                        "performance_score": stmt.excluded.performance_score,
                        "lcp_ms": stmt.excluded.lcp_ms,
                        "cls": stmt.excluded.cls,
                        "inp_ms": stmt.excluded.inp_ms,
                        "fcp_ms": stmt.excluded.fcp_ms,
                        "ttfb_ms": stmt.excluded.ttfb_ms,
                    },
                )
                await session.execute(stmt)
                saved += 1

        job_log.status = JobStatusEnum.success
        job_log.finished_at = datetime.now(UTC)
        job_log.job_metadata = {"saved": saved, "urls": len(urls)}
        await session.commit()
        log.info("pagespeed_done", tenant_id=str(tenant_id), saved=saved)
        return saved
    except Exception as exc:
        job_log.status = JobStatusEnum.failed
        job_log.error_text = f"{type(exc).__name__}: {exc}"
        job_log.finished_at = datetime.now(UTC)
        await session.commit()
        log.exception("pagespeed_failed", tenant_id=str(tenant_id))
        raise
