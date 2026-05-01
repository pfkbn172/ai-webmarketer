"""月次レポート生成ジョブ(毎月 3 日 7:00 JST)。"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text

from app.ai_engine.usecases.monthly_report import generate_monthly_report
from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.report import Report
from app.db.models.tenant import Tenant
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.services.resend_mailer import send as send_mail
from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def _previous_month_period() -> str:
    today = date.today()
    first_of_current = today.replace(day=1)
    last_of_prev = first_of_current - timedelta(days=1)
    return f"{last_of_prev.year:04d}-{last_of_prev.month:02d}"


async def job() -> None:
    period = _previous_month_period()
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            jl = JobExecutionLog(
                tenant_id=tenant_id,
                job_name="generate_monthly_report",
                status=JobStatusEnum.running,
                started_at=datetime.now(UTC),
            )
            session.add(jl)
            await session.flush()

            try:
                html = await generate_monthly_report(session, tenant_id, period=period)
                tenant = (
                    await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
                ).one()
                report = Report(
                    tenant_id=tenant_id,
                    period=period,
                    report_type="monthly",
                    summary_html=html,
                )
                session.add(report)

                if settings.mail_notify_to:
                    send_mail(
                        to=settings.mail_notify_to,
                        subject=f"[{tenant.name}] 月次レポート {period}",
                        html=html,
                    )

                jl.status = JobStatusEnum.success
                jl.finished_at = datetime.now(UTC)
                await session.commit()
            except Exception as exc:
                jl.status = JobStatusEnum.failed
                jl.error_text = f"{type(exc).__name__}: {exc}"
                jl.finished_at = datetime.now(UTC)
                await session.commit()
                log.exception("monthly_report_job_failed", tenant_id=str(tenant_id))
