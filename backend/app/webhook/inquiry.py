"""問い合わせ Webhook。

POST /marketer/webhook/inquiry/{tenant_id}
- フォーム本文を受け取り
- AI で構造化(可能なら)
- inquiries テーブルに保存
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.usecases.inquiry_structuring import structure_inquiry
from app.db.base import get_db_session
from app.db.models.enums import AiOriginEnum, InquirySourceEnum
from app.db.models.inquiry import Inquiry
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/inquiry", tags=["webhook"])


class InquiryWebhookBody(BaseModel):
    text: str
    source_channel: InquirySourceEnum = InquirySourceEnum.web
    utm_source: str | None = None  # AI 起点判定のヒント


def _ai_origin_from_utm(utm: str | None) -> AiOriginEnum | None:
    if not utm:
        return None
    u = utm.lower()
    for enum_val in AiOriginEnum:
        if enum_val.value in u:
            return enum_val
    return None


@router.post("/{tenant_id}", status_code=201)
async def receive_inquiry(
    tenant_id: uuid.UUID,
    body: InquiryWebhookBody,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # RLS のため app.tenant_id をセット
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )

    structured = await structure_inquiry(
        session, tenant_id, raw_text=body.text, source_hint=body.utm_source or ""
    )

    # ai_origin の決定: UTM ヒント優先 → AI 推定
    origin = _ai_origin_from_utm(body.utm_source)
    if origin is None and structured.get("ai_origin"):
        try:
            origin = AiOriginEnum(structured["ai_origin"])
        except ValueError:
            origin = None

    inquiry = Inquiry(
        tenant_id=tenant_id,
        received_at=datetime.now(UTC),
        industry=structured.get("industry"),
        company_size=structured.get("company_size"),
        content_text=body.text,
        source_channel=body.source_channel,
        ai_origin=origin,
        raw_payload={
            "headers": dict(request.headers),
            "body": body.model_dump(),
            "structured": structured,
        },
    )
    session.add(inquiry)
    await session.commit()
    log.info("inquiry_received", tenant_id=str(tenant_id), inquiry_id=str(inquiry.id))
    if not isinstance(structured, dict):  # pragma: no cover
        raise HTTPException(500, "AI structuring returned non-dict")
    return {"id": str(inquiry.id), "ai_origin": origin.value if origin else None}
