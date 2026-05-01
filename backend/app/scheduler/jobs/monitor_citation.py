"""AI 引用モニタジョブ。"""

from app.collectors.llm_citation.runner import run_for_tenant
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            try:
                await run_for_tenant(session, tenant_id)
            except Exception:
                log.exception("citation_monitor_job_failed", tenant_id=str(tenant_id))
