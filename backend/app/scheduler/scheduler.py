"""APScheduler 設定。

Phase 1: AsyncIOScheduler を 1 プロセス常駐(marketer-worker)で起動。
ジョブの実行ログは job_execution_logs テーブルに各ランナーが記録する。
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.jobs.collect_competitor_rss import job as job_competitor_rss
from app.scheduler.jobs.collect_ga4 import job as job_ga4
from app.scheduler.jobs.collect_gsc import job as job_gsc
from app.scheduler.jobs.generate_monthly_report import job as job_monthly
from app.scheduler.jobs.generate_weekly_summary import job as job_weekly
from app.scheduler.jobs.monitor_citation import job as job_citation
from app.utils.logger import get_logger

log = get_logger(__name__)

# 仕様書 7.1 / Q6
SCHEDULE = {
    "collect_gsc": CronTrigger(day_of_week="mon", hour=3, minute=0, timezone="Asia/Tokyo"),
    "collect_ga4": CronTrigger(day_of_week="mon", hour=3, minute=30, timezone="Asia/Tokyo"),
    "monitor_citation": CronTrigger(day_of_week="mon", hour=4, minute=0, timezone="Asia/Tokyo"),
    "collect_competitor_rss": CronTrigger(
        day_of_week="mon", hour=5, minute=0, timezone="Asia/Tokyo"
    ),
    "generate_weekly_summary": CronTrigger(
        day_of_week="mon", hour=6, minute=0, timezone="Asia/Tokyo"
    ),
    # Q6: 毎月 3 日 7:00 JST(GSC/GA4 確定遅延を吸収)
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
    log.info("scheduler_built", jobs=list(SCHEDULE.keys()))
    return scheduler
