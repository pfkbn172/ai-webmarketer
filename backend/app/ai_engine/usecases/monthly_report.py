"""月次レポート生成ユースケース(Phase 2 拡張版)。

business_context・クラスタ別引用率・違和感・引用機会を全部渡して、
プロのマーケター視点の戦略レビューを生成する。
"""

import json
import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.ai_engine.usecases.citation_opportunity import find_opportunities
from app.db.models.citation_log import CitationLog
from app.db.models.content import Content
from app.db.models.enums import AIUseCaseEnum
from app.db.models.kpi_log import KpiLog
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.services.anomaly_detector import detect as detect_anomalies
from app.utils.logger import get_logger

log = get_logger(__name__)


async def _cluster_citation_breakdown(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> dict[str, dict]:
    """クラスタ別の引用率を集計。"""
    queries = list(
        (
            await session.scalars(
                select(TargetQuery).where(TargetQuery.tenant_id == tenant_id)
            )
        ).all()
    )
    qmap = {q.id: q.cluster_id or "unknown" for q in queries}
    logs = list(
        (
            await session.scalars(
                select(CitationLog).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_date.between(start, end),
                )
            )
        ).all()
    )
    by_cluster: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "self_cited": 0}
    )
    for log_ in logs:
        cluster = qmap.get(log_.query_id, "unknown")
        by_cluster[cluster]["total"] += 1
        if log_.self_cited:
            by_cluster[cluster]["self_cited"] += 1
    out: dict[str, dict] = {}
    for c, v in by_cluster.items():
        rate = v["self_cited"] / v["total"] if v["total"] else 0
        out[c] = {"total": v["total"], "self_cited": v["self_cited"], "rate": rate}
    return out


async def generate_monthly_report(
    session: AsyncSession, tenant_id: uuid.UUID, *, period: str
) -> str:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}

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
    contents = list(
        (
            await session.scalars(
                select(Content).where(Content.tenant_id == tenant_id).limit(50)
            )
        ).all()
    )

    cluster_breakdown = await _cluster_citation_breakdown(session, tenant_id, start, end)
    opportunities = await find_opportunities(session, tenant_id, lookback_days=30)
    anomalies = await detect_anomalies(session, tenant_id)

    prompt = render(
        "monthly_report.md",
        {
            "tenant_name": tenant.name,
            "period": period,
            "industry": tenant.industry or "(未設定)",
            "stage": bc.get("stage", "(未設定)"),
            "geographic_base": ", ".join(bc.get("geographic_base", [])) or "(未設定)",
            "geographic_expansion": ", ".join(bc.get("geographic_expansion", []))
            or "(未設定)",
            "unique_value": ", ".join(bc.get("unique_value", [])) or "(未設定)",
            "primary_offerings": ", ".join(bc.get("primary_offerings", []))
            or "(未設定)",
            "target_customer": bc.get("target_customer", "(未設定)"),
            "weak_segments": ", ".join(bc.get("weak_segments", [])) or "(なし)",
            "strong_segments": ", ".join(bc.get("strong_segments", [])) or "(なし)",
            "kpi_summary": json.dumps(
                [
                    {
                        "date": str(r.date),
                        "sessions": r.sessions,
                        "ai_citations": r.ai_citation_count,
                        "named_search": r.named_search_count,
                    }
                    for r in kpi_rows[-10:]
                ],
                ensure_ascii=False,
            ),
            "citation_trend": "過去 30 日の citation_logs 集計済",
            "cluster_citation_breakdown": json.dumps(cluster_breakdown, ensure_ascii=False),
            "citation_opportunities": json.dumps(opportunities[:5], ensure_ascii=False),
            "schema_coverage": "(W2-04 で監査ジョブ実行後に充実)",
            "contents": json.dumps(
                [{"title": c.title, "url": c.url} for c in contents[:10]],
                ensure_ascii=False,
            ),
            "inquiries_summary": "(W4-01 で集計)",
            "anomalies": json.dumps(
                [
                    {"kind": a.kind, "detail": a.detail, "severity": a.severity}
                    for a in anomalies
                ],
                ensure_ascii=False,
            ),
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.monthly_report
    )
    res = await provider.generate(
        system_prompt=(
            "あなたは中小企業向け SEO/LLMO の戦略コンサルタントです。"
            "事実ベースで断言し、根拠は事業文脈と数字の両方から引きます。"
        ),
        user_prompt=prompt,
        max_tokens=6000,
        temperature=0.4,
    )
    log.info(
        "monthly_report_generated",
        tenant_id=str(tenant_id),
        period=period,
        tokens=res.usage.total_tokens,
    )
    return res.text
