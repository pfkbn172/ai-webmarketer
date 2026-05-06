"""競合見出し収集ジョブ(月次)。

competitors.is_active = true のドメインに対して、target_urls(あれば)+ トップページの
title/h1/h2/h3 を抽出して keyword_suggestions に保存する。
スクレイプはレート制限+robots.txt 尊重。月初 1日 5:00 JST。
"""

from app.keyword_engine.headings_runner import run_for_tenant
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
                    "competitor_headings_job_failed", tenant_id=str(tenant_id)
                )
