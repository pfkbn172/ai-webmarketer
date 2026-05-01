"""引用機会分析: 競合は引用されているがクライアントは引用されていないクエリを抽出。"""

import json
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.citation_log import CitationLog
from app.db.models.enums import AIUseCaseEnum
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def find_opportunities(
    session: AsyncSession, tenant_id: uuid.UUID, *, lookback_days: int = 30
) -> list[dict]:
    """各クエリについて自社引用 0 / 競合引用 >0 を抽出。"""
    end = date.today()
    start = end - timedelta(days=lookback_days)

    queries = list(
        (
            await session.scalars(
                select(TargetQuery).where(
                    TargetQuery.tenant_id == tenant_id,
                    TargetQuery.is_active.is_(True),
                )
            )
        ).all()
    )
    out: list[dict] = []
    for q in queries:
        logs = list(
            (
                await session.scalars(
                    select(CitationLog).where(
                        CitationLog.tenant_id == tenant_id,
                        CitationLog.query_id == q.id,
                        CitationLog.query_date.between(start, end),
                    )
                )
            ).all()
        )
        if not logs:
            continue
        self_count = sum(1 for log_ in logs if log_.self_cited)
        competitor_count = sum(
            sum((c.get("count", 1) for c in (log_.competitor_cited or [])), 0) for log_ in logs
        )
        if self_count == 0 and competitor_count > 0:
            out.append(
                {
                    "query": q.query_text,
                    "competitor_examples": [
                        c["domain"] for log_ in logs[:3] for c in (log_.competitor_cited or [])
                    ][:5],
                }
            )
    return out


async def suggest_actions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    opportunities: list[dict],
) -> list[dict]:
    """各機会に対して AI が推奨アクションを提案する。"""
    if not opportunities:
        return []
    tenant = (await session.scalars(select(Tenant).where(Tenant.id == tenant_id))).one()
    prompt = render(
        "citation_opportunity.md",
        {
            "tenant_name": tenant.name,
            "domain": tenant.domain,
            "opportunities": opportunities,
        },
    )
    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.citation_opportunity
    )
    res = await provider.generate(
        system_prompt="あなたは LLMO の専門家です。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=2000,
        temperature=0.4,
    )
    try:
        return json.loads(res.text)
    except json.JSONDecodeError:
        log.warning("citation_opportunity_invalid_json", raw=res.text[:200])
        return []
