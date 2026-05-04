"""アラート評価ジョブ(週次)。"""

from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.services.alert_evaluator import evaluate_and_notify
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            try:
                fired = await evaluate_and_notify(session, tenant_id)
                log.info("alerts_evaluated", tenant_id=str(tenant_id), fired=fired)
            except Exception:
                log.exception("alerts_job_failed", tenant_id=str(tenant_id))
