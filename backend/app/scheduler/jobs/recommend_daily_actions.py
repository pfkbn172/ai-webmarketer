"""毎日の3アクション生成ジョブ(毎朝 6:45 JST)。

evaluate_alerts(6:30) の15分後に走り、最新 KPI/ユニバース/引用機会 を踏まえた
アクションをホーム画面用に生成する。
"""

from datetime import UTC, datetime

from app.ai_engine.usecases.daily_action import recommend_daily_actions
from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "recommend_daily_actions"


async def job() -> None:
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
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
                await recommend_daily_actions(session, tenant_id)
                job_log.status = JobStatusEnum.success
            except Exception:
                log.exception("daily_action_job_failed", tenant_id=str(tenant_id))
                job_log.status = JobStatusEnum.failed
            finally:
                job_log.finished_at = datetime.now(UTC)
                await session.commit()
