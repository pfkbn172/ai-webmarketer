"""APScheduler 設定。

Phase 1: AsyncIOScheduler を 1 プロセス常駐(marketer-worker)で起動。
ジョブの実行ログは job_execution_logs テーブルに各ランナーが記録する。
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.jobs.collect_competitor_rss import job as job_competitor_rss
from app.scheduler.jobs.collect_ga4 import job as job_ga4
from app.scheduler.jobs.collect_gsc import job as job_gsc
from app.scheduler.jobs.collect_pagespeed import job as job_pagespeed
from app.scheduler.jobs.evaluate_alerts import job as job_alerts
from app.scheduler.jobs.generate_monthly_report import job as job_monthly
from app.scheduler.jobs.generate_weekly_summary import job as job_weekly
from app.scheduler.jobs.monitor_citation import job as job_citation
from app.utils.logger import get_logger

log = get_logger(__name__)

# 仕様書 7.1 / Q6
# データ収集系は毎日実行(API 叩く処理は軽く、UPSERT で冪等)。
# 過去 7 日を毎回再取得することで GSC/GA4 のデータ確定遅延と欠損を吸収する。
# レポート生成系は週次・月次のまま(ユーザー向け納品物なので頻度を上げない)。
SCHEDULE = {
    "collect_gsc": CronTrigger(hour=3, minute=0, timezone="Asia/Tokyo"),
    "collect_ga4": CronTrigger(hour=3, minute=30, timezone="Asia/Tokyo"),
    "monitor_citation": CronTrigger(hour=4, minute=0, timezone="Asia/Tokyo"),
    "collect_competitor_rss": CronTrigger(hour=5, minute=0, timezone="Asia/Tokyo"),
    # PageSpeed Insights は TOP URL を 1 サイトあたり数十 URL 計測する程度
    "collect_pagespeed": CronTrigger(hour=5, minute=30, timezone="Asia/Tokyo"),
    # アラートは GSC/GA4 取り込み後の毎日 6:30
    "evaluate_alerts": CronTrigger(hour=6, minute=30, timezone="Asia/Tokyo"),
    # 週次サマリは月曜のまま
    "generate_weekly_summary": CronTrigger(
        day_of_week="mon", hour=6, minute=0, timezone="Asia/Tokyo"
    ),
    # 月次レポートは毎月 3 日 7:00 JST(GSC/GA4 確定遅延を吸収)
    "generate_monthly_report": CronTrigger(day=3, hour=7, minute=0, timezone="Asia/Tokyo"),
}


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(job_gsc, SCHEDULE["collect_gsc"], id="collect_gsc")
    scheduler.add_job(job_ga4, SCHEDULE["collect_ga4"], id="collect_ga4")
    scheduler.add_job(job_citation, SCHEDULE["monitor_citation"], id="monitor_citation")
    scheduler.add_job(
        job_competitor_rss, SCHEDULE["collect_competitor_rss"], id="collect_competitor_rss"
    )
    scheduler.add_job(
        job_weekly, SCHEDULE["generate_weekly_summary"], id="generate_weekly_summary"
    )
    scheduler.add_job(
        job_monthly, SCHEDULE["generate_monthly_report"], id="generate_monthly_report"
    )
    scheduler.add_job(job_alerts, SCHEDULE["evaluate_alerts"], id="evaluate_alerts")
    scheduler.add_job(job_pagespeed, SCHEDULE["collect_pagespeed"], id="collect_pagespeed")
    log.info("scheduler_built", jobs=list(SCHEDULE.keys()))
    return scheduler
