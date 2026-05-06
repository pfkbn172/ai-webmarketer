"""キーワードユニバース集計ジョブ(週次)。

GSC実績/サジェスト派生数/競合カバー/LLM引用率を統合し、
keyword_universe テーブルに upsert する。collect_keyword_suggestions の後に走る。
"""

from datetime import UTC, datetime

from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.keyword_engine.aggregator import aggregate_universe
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)

JOB_NAME = "aggregate_keyword_universe"


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
                await aggregate_universe(session, tenant_id)
                job_log.status = JobStatusEnum.success
            except Exception:
                log.exception(
                    "keyword_universe_aggregate_failed", tenant_id=str(tenant_id)
                )
                job_log.status = JobStatusEnum.failed
            finally:
                job_log.finished_at = datetime.now(UTC)
                await session.commit()
