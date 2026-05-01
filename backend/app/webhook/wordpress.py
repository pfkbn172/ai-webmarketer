"""WordPress 公開トリガー Webhook。

POST /marketer/webhook/wordpress/{tenant_id}
- WP からの POST(post_id, url, title, content)を受信
- contents 台帳に upsert(URL UNIQUE)
- 構造化データ自動付与は W2-02 のサービスを呼ぶ(TODO)
- llms.txt 更新 / SNS / MEO は今後のチケットで
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session
from app.db.models.content import Content
from app.db.models.enums import ContentStatusEnum
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/wordpress", tags=["webhook"])


class WordPressPublishBody(BaseModel):
    post_id: int
    url: str
    title: str
    content_html: str | None = None


@router.post("/{tenant_id}", status_code=201)
async def receive_publish(
    tenant_id: uuid.UUID,
    body: WordPressPublishBody,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    existing = (
        await session.scalars(
            select(Content).where(
                Content.tenant_id == tenant_id, Content.url == body.url
            )
        )
    ).one_or_none()

    now = datetime.now(UTC)
    if existing:
        existing.title = body.title
        existing.status = ContentStatusEnum.published
        existing.published_at = now
        existing.wp_post_id = body.post_id
        action = "updated"
    else:
        existing = Content(
            tenant_id=tenant_id,
            url=body.url,
            title=body.title,
            status=ContentStatusEnum.published,
            published_at=now,
            wp_post_id=body.post_id,
        )
        session.add(existing)
        action = "created"

    await session.commit()
    log.info(
        "wordpress_publish_received",
        tenant_id=str(tenant_id),
        action=action,
        content_id=str(existing.id),
        url=body.url,
    )
    return {"id": str(existing.id), "action": action}
