"""llms.txt 自動生成サービス。

LLM フレンドリーなサイト概要を提供する。仕様書 4.2.3:
- サイト概要 / 主要記事一覧 / 著者情報 / ライセンス
- 記事公開時に自動更新
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.author_profile import AuthorProfile
from app.db.models.content import Content
from app.db.models.enums import ContentStatusEnum
from app.db.models.tenant import Tenant


async def generate(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()

    contents = list(
        (
            await session.scalars(
                select(Content)
                .where(
                    Content.tenant_id == tenant_id,
                    Content.status == ContentStatusEnum.published,
                )
                .order_by(Content.published_at.desc())
                .limit(50)
            )
        ).all()
    )

    primary_author = (
        await session.scalars(
            select(AuthorProfile).where(
                AuthorProfile.tenant_id == tenant_id,
                AuthorProfile.is_primary.is_(True),
            )
        )
    ).one_or_none()

    lines: list[str] = []
    lines.append(f"# {tenant.name}")
    lines.append("")
    if tenant.industry:
        lines.append(f"> 業種: {tenant.industry}")
    lines.append(f"> サイト: https://{tenant.domain}/")
    lines.append("")

    if primary_author:
        lines.append("## 著者")
        lines.append(f"- {primary_author.name}({primary_author.job_title or ''})")
        if primary_author.bio_short:
            lines.append(f"  - {primary_author.bio_short}")
        lines.append("")

    if contents:
        lines.append("## 主要記事")
        for c in contents:
            lines.append(f"- [{c.title}]({c.url})")
        lines.append("")

    lines.append("## ライセンス")
    lines.append("引用は出典明記のうえご利用ください。")
    return "\n".join(lines) + "\n"
