"""記事改善ユースケース。

既存記事を AI に評価させて、LLMO 引用獲得のための具体的改善提案を出す。
冒頭定義文・表・FAQ・E-E-A-T シグナル・地域具体性・独自性活用 の 6 観点。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.json_parse import parse_json_object
from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.content import Content
from app.db.models.enums import AIUseCaseEnum
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def improve_content(
    session: AsyncSession, tenant_id: uuid.UUID, content_id: uuid.UUID
) -> dict:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    content = (
        await session.scalars(
            select(Content).where(
                Content.tenant_id == tenant_id, Content.id == content_id
            )
        )
    ).one_or_none()
    if not content:
        raise ValueError(f"content {content_id} not found")
    bc = tenant.business_context or {}

    excerpt = (content.draft_md or "")[:2000] or "(本文未取得)"

    prompt = render(
        "content_improvement.md",
        {
            "tenant_name": tenant.name,
            "unique_value": ", ".join(bc.get("unique_value", [])) or "(未設定)",
            "primary_offerings": ", ".join(bc.get("primary_offerings", []))
            or "(未設定)",
            "geographic_base": ", ".join(bc.get("geographic_base", []))
            or "(未設定)",
            "title": content.title,
            "url": content.url or "(未設定)",
            "excerpt": excerpt,
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.content_draft
    )
    res = await provider.generate(
        system_prompt="あなたは LLMO(LLM 引用最適化)の専門家です。",
        user_prompt=prompt,
        response_format="json",
        max_tokens=3000,
        temperature=0.3,
    )
    log.info(
        "content_improvement_done",
        tenant_id=str(tenant_id),
        content_id=str(content_id),
        tokens=res.usage.total_tokens,
    )
    return parse_json_object(res.text, log_label="content_improvement_json")
