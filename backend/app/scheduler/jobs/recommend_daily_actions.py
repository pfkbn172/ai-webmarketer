"""毎日の3アクション生成ジョブ(毎朝 6:45 JST)。

evaluate_alerts(6:30) の15分後に走り、最新 KPI/ユニバース/引用機会 を踏まえた
アクションをホーム画面用に生成する。
"""

from datetime import UTC, datetime

from sqlalchemy import text

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
            # RLS の app.tenant_id を設定。これを忘れると tenants / 各種テーブルから
            # 0 行しか取れず recommend_daily_actions が NoResultFound で落ちる。
            # 第3引数 false でセッションスコープに設定 — recommend_daily_actions は
            # 内部で commit() を呼んだ後に session.refresh() するため、トランザクション
            # スコープ(true)だと commit でリセットされて refresh が失敗する。
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, false)"),
                {"tid": str(tenant_id)},
            )

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
            except Exception as exc:
                log.exception("daily_action_job_failed", tenant_id=str(tenant_id))
                job_log.status = JobStatusEnum.failed
                job_log.error_text = f"{type(exc).__name__}: {exc}"
            finally:
                job_log.finished_at = datetime.now(UTC)
                await session.commit()
