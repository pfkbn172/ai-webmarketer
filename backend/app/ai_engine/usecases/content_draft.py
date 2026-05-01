"""コンテンツドラフト生成ユースケース。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.author_profile import AuthorProfile
from app.db.models.content import Content
from app.db.models.enums import AIUseCaseEnum, ContentStatusEnum
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def generate_draft(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    title: str,
    target_query: str,
    outline: list[str],
    compliance_rules: list[str] | None = None,
) -> Content:
    """ドラフトを生成し、contents に保存して返す。"""
    tenant = (await session.scalars(select(Tenant).where(Tenant.id == tenant_id))).one()
    primary_author = (
        await session.scalars(
            select(AuthorProfile).where(
                AuthorProfile.tenant_id == tenant_id,
                AuthorProfile.is_primary.is_(True),
            )
        )
    ).one_or_none()
    author_text = (
        f"{primary_author.name} ({primary_author.job_title or ''})"
        if primary_author
        else "(未登録)"
    )

    prompt = render(
        "content_draft.md",
        {
            "title": title,
            "target_query": target_query,
            "outline": outline,
            "tenant_name": tenant.name,
            "industry": tenant.industry or "",
            "author_profile": author_text,
            "compliance_rules": compliance_rules or [],
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.content_draft
    )
    res = await provider.generate(
        system_prompt="あなたはプロのライターです。",
        user_prompt=prompt,
        max_tokens=4000,
        temperature=0.6,
    )

    content = Content(
        tenant_id=tenant_id,
        title=title,
        status=ContentStatusEnum.review,
        draft_md=res.text,
        primary_author_id=primary_author.id if primary_author else None,
    )
    session.add(content)
    await session.flush()
    log.info(
        "content_draft_generated",
        tenant_id=str(tenant_id),
        content_id=str(content.id),
        tokens=res.usage.total_tokens,
    )
    return content
