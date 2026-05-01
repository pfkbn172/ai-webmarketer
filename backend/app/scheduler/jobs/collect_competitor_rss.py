"""競合 RSS 収集ジョブ。"""

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.collectors.competitor_rss.client import fetch_feed
from app.db.models.competitor import Competitor
from app.db.models.competitor_post import CompetitorPost
from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            started = datetime.now(UTC)
            jl = JobExecutionLog(
                tenant_id=tenant_id,
                job_name="collect_competitor_rss",
                status=JobStatusEnum.running,
                started_at=started,
            )
            session.add(jl)
            await session.flush()

            try:
                competitors = list(
                    (
                        await session.scalars(
                            select(Competitor).where(
                                Competitor.tenant_id == tenant_id,
                                Competitor.is_active.is_(True),
                                Competitor.rss_url.isnot(None),
                            )
                        )
                    ).all()
                )
                total_inserted = 0
                for c in competitors:
                    try:
                        entries = await fetch_feed(c.rss_url)
                    except Exception as exc:
                        log.warning(
                            "rss_fetch_failed",
                            competitor=c.domain,
                            error=str(exc),
                        )
                        continue
                    for e in entries:
                        if not e.url:
                            continue
                        stmt = pg_insert(CompetitorPost).values(
                            tenant_id=tenant_id,
                            competitor_id=c.id,
                            url=e.url,
                            title=e.title,
                            published_at=e.published_at,
                            summary=e.summary,
                        )
                        stmt = stmt.on_conflict_do_nothing(
                            constraint="uq_competitor_posts_url"
                        )
                        await session.execute(stmt)
                        total_inserted += 1
                jl.status = JobStatusEnum.success
                jl.finished_at = datetime.now(UTC)
                jl.job_metadata = {"competitors": len(competitors), "entries": total_inserted}
                await session.commit()
            except Exception as exc:
                jl.status = JobStatusEnum.failed
                jl.finished_at = datetime.now(UTC)
                jl.error_text = f"{type(exc).__name__}: {exc}"
                await session.commit()
                log.exception("competitor_rss_failed", tenant_id=str(tenant_id))
