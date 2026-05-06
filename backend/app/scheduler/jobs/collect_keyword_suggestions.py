"""キーワードサジェスト収集ジョブ(週次)。

Google + Bing から business_context 由来のシードに対する派生語を取得し、
keyword_suggestions テーブルに保存する。Phase 2 の集計ジョブの入力データ源。
"""

from app.keyword_engine.runner import run_for_tenant
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            try:
                await run_for_tenant(session, tenant_id)
            except Exception:
                log.exception(
                    "keyword_suggestions_job_failed", tenant_id=str(tenant_id)
                )
