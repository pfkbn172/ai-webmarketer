"""クエリ提案ユースケース。

business_context を踏まえて Gemini に「現実的に勝てるクエリ 15〜20 本」を
提案させる。Phase 2 戦略思考レイヤーの中核。
"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.enums import AIUseCaseEnum
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def suggest_queries(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[dict]:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}

    existing = list(
        (
            await session.scalars(
                select(TargetQuery).where(
                    TargetQuery.tenant_id == tenant_id,
                    TargetQuery.is_active.is_(True),
                )
            )
        ).all()
    )

    prompt = render(
        "query_suggestion.md",
        {
            "tenant_name": tenant.name,
            "industry": tenant.industry or "(未設定)",
            "domain": tenant.domain,
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
            "existing_queries": [q.query_text for q in existing],
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.theme_suggestion
    )
    res = await provider.generate(
        system_prompt="あなたは中小企業向け SEO/LLMO 戦略コンサルタントです。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=4000,
        temperature=0.5,
    )
    log.info(
        "query_suggestion_done",
        tenant_id=str(tenant_id),
        tokens=res.usage.total_tokens,
    )
    try:
        suggestions = json.loads(res.text)
    except json.JSONDecodeError:
        log.warning("query_suggestion_invalid_json", raw=res.text[:200])
        return []
    return suggestions if isinstance(suggestions, list) else []
