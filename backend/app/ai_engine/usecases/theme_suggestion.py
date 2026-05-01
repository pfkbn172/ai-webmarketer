"""テーマ提案ユースケース。

引用機会分析の結果と著者プロフィールを組み合わせて、コンテンツテーマを 5 件提案する。
Provider は AIProviderFactory 経由で取得(用途別に切替可能)。
"""

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.ai_engine.template_loader import render
from app.db.models.author_profile import AuthorProfile
from app.db.models.enums import AIUseCaseEnum
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)


async def suggest_themes(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    missed_queries: list[str],
) -> list[dict[str, Any]]:
    """5 件のテーマ提案を JSON 配列で返す。"""
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    primary_author = (
        await session.scalars(
            select(AuthorProfile).where(
                AuthorProfile.tenant_id == tenant_id,
                AuthorProfile.is_primary.is_(True),
            )
        )
    ).one_or_none()

    author_profile_text = (
        f"{primary_author.name} ({primary_author.job_title or ''})"
        if primary_author
        else "(著者プロフィール未登録)"
    )

    prompt = render(
        "theme_suggestion.md",
        {
            "tenant_name": tenant.name,
            "industry": tenant.industry or "",
            "domain": tenant.domain,
            "missed_queries": missed_queries,
            "author_profile": author_profile_text,
        },
    )

    provider = await AIProviderFactory.get_for_use_case(
        session, tenant_id, AIUseCaseEnum.theme_suggestion
    )
    res = await provider.generate(
        system_prompt="You are a Japanese content strategy expert.",
        user_prompt=prompt,
        response_format="json",
        max_tokens=2000,
        temperature=0.5,
    )
    log.info(
        "theme_suggestion_done",
        tenant_id=str(tenant_id),
        usage_tokens=res.usage.total_tokens,
    )

    try:
        themes = json.loads(res.text)
    except json.JSONDecodeError:
        log.warning("theme_suggestion_invalid_json", raw=res.text[:200])
        return []
    return themes if isinstance(themes, list) else []
