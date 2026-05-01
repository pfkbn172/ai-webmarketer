"""月次レポート生成ユースケース。"""

import json
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.citation_log import CitationLog
from app.db.models.content import Content
from app.db.models.enums import AIUseCaseEnum
from app.db.models.kpi_log import KpiLog
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def generate_monthly_report(
    session: AsyncSession, tenant_id: uuid.UUID, *, period: str
) -> str:
    """period: 'YYYY-MM' のレポートを HTML で生成して返す。"""
    tenant = (await session.scalars(select(Tenant).where(Tenant.id == tenant_id))).one()

    # 過去 30 日のサマリを集計
    end = date.today()
    start = end - timedelta(days=30)
    kpi_rows = list(
        (
            await session.scalars(
                select(KpiLog)
                .where(KpiLog.tenant_id == tenant_id, KpiLog.date.between(start, end))
                .order_by(KpiLog.date)
            )
        ).all()
    )
    citation_rows = list(
        (
            await session.scalars(
                select(CitationLog)
                .where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_date.between(start, end),
                )
                .limit(500)
            )
        ).all()
    )
    contents = list(
        (
            await session.scalars(
                select(Content).where(Content.tenant_id == tenant_id).limit(50)
            )
        ).all()
    )

    kpi_summary = json.dumps(
        [
            {
                "date": str(r.date),
                "sessions": r.sessions,
                "ai_citations": r.ai_citation_count,
            }
            for r in kpi_rows[-10:]
        ],
        ensure_ascii=False,
    )
    citation_trend = f"{len(citation_rows)} citation log entries in last 30 days"
    citation_opportunities = "(W3-04 で本実装)"
    schema_coverage = "(W2-04 のスコア集計を後で組み込む)"
    contents_str = json.dumps(
        [{"title": c.title, "url": c.url} for c in contents[:10]], ensure_ascii=False
    )
    inquiries_summary = "(W4-01 で集計)"

    prompt = render(
        "monthly_report.md",
        {
            "tenant_name": tenant.name,
            "period": period,
            "kpi_summary": kpi_summary,
            "citation_trend": citation_trend,
            "citation_opportunities": citation_opportunities,
            "schema_coverage": schema_coverage,
            "contents": contents_str,
            "inquiries_summary": inquiries_summary,
        },
    )
    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.monthly_report
    )
    res = await provider.generate(
        system_prompt="あなたは Web マーケティングのアナリストです。",
        user_prompt=prompt,
        max_tokens=4000,
        temperature=0.4,
    )
    log.info(
        "monthly_report_generated",
        tenant_id=str(tenant_id),
        period=period,
        tokens=res.usage.total_tokens,
    )
    return res.text
