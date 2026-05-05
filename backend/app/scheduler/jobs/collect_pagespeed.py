"""PageSpeed Insights 週次収集ジョブ。"""

from app.collectors.pagespeed.runner import run_for_tenant
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            try:
                await run_for_tenant(session, tenant_id, top_n=5)
            except Exception:
                log.exception("pagespeed_job_failed", tenant_id=str(tenant_id))
