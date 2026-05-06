"""コンテンツブリーフ API。

- POST /content-briefs/generate           採用キーワード群からブリーフ生成
- GET  /content-briefs                    一覧
- GET  /content-briefs/{id}               詳細
- POST /content-briefs/{id}/publish-wp    WordPress 下書きとして送出
- DELETE /content-briefs/{id}             削除
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.usecases.content_brief import generate_brief
from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.content_brief import ContentBrief
from app.db.models.tenant_credential import TenantCredential  # noqa: F401  (model load)
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.services.wordpress_publisher import get_wp_client
from app.utils.logger import get_logger

router = APIRouter(prefix="/content-briefs", tags=["content_briefs"])
log = get_logger(__name__)


class GenerateIn(BaseModel):
    primary_keyword: str
    related_keyword_ids: list[uuid.UUID] = []


class H2Item(BaseModel):
    h2: str
    target_keywords: list[str] = []
    rationale: str | None = None


class ContentBriefOut(BaseModel):
    id: uuid.UUID
    primary_keyword: str
    cluster_ids: list[str]
    selected_keywords: list[str]
    title: str
    meta_description: str | None
    h2_outline: list[H2Item]
    related_keywords: list[str]
    target_url_slug: str | None
    rationale: str | None
    status: str
    wp_draft_id: int | None
    created_at: datetime
    updated_at: datetime


class PublishResult(BaseModel):
    wp_draft_id: int
    wp_post_url: str | None = None


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def _to_out(b: ContentBrief) -> ContentBriefOut:
    return ContentBriefOut(
        id=b.id,
        primary_keyword=b.primary_keyword,
        cluster_ids=list(b.cluster_ids or []),
        selected_keywords=list(b.selected_keywords or []),
        title=b.title,
        meta_description=b.meta_description,
        h2_outline=[H2Item(**(item if isinstance(item, dict) else {})) for item in (b.h2_outline or [])],
        related_keywords=list(b.related_keywords or []),
        target_url_slug=b.target_url_slug,
        rationale=b.rationale,
        status=b.status,
        wp_draft_id=b.wp_draft_id,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


@router.post("/generate", response_model=ContentBriefOut)
async def generate(
    payload: GenerateIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ContentBriefOut:
    await _set_ctx(session, tenant_id)
    try:
        brief = await generate_brief(
            session,
            tenant_id,
            primary_keyword=payload.primary_keyword,
            related_keyword_ids=payload.related_keyword_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_out(brief)


@router.get("", response_model=list[ContentBriefOut])
async def list_briefs(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ContentBriefOut]:
    await _set_ctx(session, tenant_id)
    stmt = select(ContentBrief).where(ContentBrief.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(ContentBrief.status == status_filter)
    stmt = stmt.order_by(desc(ContentBrief.created_at)).limit(limit)
    rows = list((await session.scalars(stmt)).all())
    return [_to_out(b) for b in rows]


@router.get("/{brief_id}", response_model=ContentBriefOut)
async def get_brief(
    brief_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ContentBriefOut:
    await _set_ctx(session, tenant_id)
    b = (
        await session.scalars(
            select(ContentBrief).where(
                ContentBrief.tenant_id == tenant_id,
                ContentBrief.id == brief_id,
            )
        )
    ).one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Brief not found")
    return _to_out(b)


@router.delete("/{brief_id}")
async def delete_brief(
    brief_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _set_ctx(session, tenant_id)
    b = (
        await session.scalars(
            select(ContentBrief).where(
                ContentBrief.tenant_id == tenant_id,
                ContentBrief.id == brief_id,
            )
        )
    ).one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Brief not found")
    await session.delete(b)
    await session.commit()
    return {"ok": True}


def _render_brief_body(brief: ContentBrief) -> str:
    """ブリーフを WordPress に貼り付けるための HTML 雛形を生成する。

    title は別フィールドなので body には含めない。h2 ごとに <h2> + 短い導入段落。
    """
    parts: list[str] = []
    if brief.meta_description:
        parts.append(f"<!-- meta_description: {brief.meta_description} -->")
    if brief.rationale:
        parts.append(f"<!-- rationale: {brief.rationale} -->")
    parts.append("<p>(導入文をここに記述)</p>")
    for item in brief.h2_outline or []:
        if not isinstance(item, dict):
            continue
        h2 = item.get("h2") or ""
        targets = item.get("target_keywords") or []
        rationale = item.get("rationale") or ""
        parts.append(f"<h2>{h2}</h2>")
        if rationale:
            parts.append(f"<!-- rationale: {rationale} -->")
        if targets:
            parts.append(
                "<!-- target_keywords: " + ", ".join(targets) + " -->"
            )
        parts.append("<p>(本文をここに記述)</p>")
    if brief.related_keywords:
        parts.append(
            "<!-- related_keywords: " + ", ".join(brief.related_keywords) + " -->"
        )
    return "\n".join(parts)


@router.post("/{brief_id}/publish-wp", response_model=PublishResult)
async def publish_to_wp(
    brief_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> PublishResult:
    await _set_ctx(session, tenant_id)
    b = (
        await session.scalars(
            select(ContentBrief).where(
                ContentBrief.tenant_id == tenant_id,
                ContentBrief.id == brief_id,
            )
        )
    ).one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Brief not found")

    repo = TenantCredentialRepository(session)
    client = await get_wp_client(repo, tenant_id)
    if not client:
        raise HTTPException(
            status_code=400,
            detail="WordPress credential not configured for this tenant",
        )

    try:
        result = await client.create_draft(
            title=b.title,
            content=_render_brief_body(b),
            slug=b.target_url_slug,
            excerpt=b.meta_description,
            meta_description=b.meta_description,
        )
    except Exception as exc:
        log.exception("wp_draft_create_failed", brief_id=str(brief_id))
        raise HTTPException(status_code=502, detail=f"WordPress error: {exc}")

    post_id = int(result.get("id") or 0)
    if not post_id:
        raise HTTPException(status_code=502, detail="WordPress did not return post id")

    b.wp_draft_id = post_id
    b.status = "adopted"
    await session.commit()

    return PublishResult(
        wp_draft_id=post_id,
        wp_post_url=result.get("link"),
    )
