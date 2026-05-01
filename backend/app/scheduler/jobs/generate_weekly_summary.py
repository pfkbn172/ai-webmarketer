"""週次サマリ生成ジョブ(月曜 6:00 JST)。"""

import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.enums import AIUseCaseEnum, JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.kpi_log import KpiLog
from app.db.models.report import Report
from app.db.models.tenant import Tenant
from app.scheduler.jobs._helpers import active_tenant_ids, make_session
from app.services.resend_mailer import send as send_mail
from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


async def job() -> None:
    today = date.today()
    period = f"{today.year:04d}-W{today.isocalendar().week:02d}"
    for tenant_id in active_tenant_ids():
        async with make_session() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            jl = JobExecutionLog(
                tenant_id=tenant_id,
                job_name="generate_weekly_summary",
                status=JobStatusEnum.running,
                started_at=datetime.now(UTC),
            )
            session.add(jl)
            await session.flush()

            try:
                tenant = (
                    await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
                ).one()
                end = today
                start = end - timedelta(days=7)
                kpi_rows = list(
                    (
                        await session.scalars(
                            select(KpiLog)
                            .where(
                                KpiLog.tenant_id == tenant_id,
                                KpiLog.date.between(start, end),
                            )
                            .order_by(KpiLog.date)
                        )
                    ).all()
                )
                kpi_summary = json.dumps(
                    [
                        {"date": str(r.date), "sessions": r.sessions}
                        for r in kpi_rows[-7:]
                    ],
                    ensure_ascii=False,
                )
                prompt = render(
                    "weekly_summary.md",
                    {
                        "tenant_name": tenant.name,
                        "kpi_summary": kpi_summary,
                        "anomalies": "(W3-05 で本実装)",
                        "recent_activities": "",
                    },
                )
                provider = await AIProviderFactory.get_for_use_case(
                    session, tenant_id, AIUseCaseEnum.weekly_summary
                )
                res = await provider.generate(
                    system_prompt="あなたは Web マーケティングの分析者です。",
                    user_prompt=prompt,
                    max_tokens=800,
                    temperature=0.4,
                )

                report = Report(
                    tenant_id=tenant_id,
                    period=period[:7],  # CHAR(7) なので 'YYYY-MM' 部のみ採用
                    report_type="weekly",
                    summary_html=f"<pre>{res.text}</pre>",
                )
                session.add(report)
                if settings.mail_notify_to:
                    send_mail(
                        to=settings.mail_notify_to,
                        subject=f"[{tenant.name}] 週次サマリ {period}",
                        html=f"<pre>{res.text}</pre>",
                    )

                jl.status = JobStatusEnum.success
                jl.finished_at = datetime.now(UTC)
                await session.commit()
            except Exception as exc:
                jl.status = JobStatusEnum.failed
                jl.error_text = f"{type(exc).__name__}: {exc}"
                jl.finished_at = datetime.now(UTC)
                await session.commit()
                log.exception("weekly_summary_failed", tenant_id=str(tenant_id))
