"""問い合わせ管理 API(手入力 + 一覧 + ステータス更新)。

仕様書 4.4.2 / 4.5.7。Webhook 経由(/webhook/inquiry)で自動受信されるが、
電話・口頭メモ等で受けた分は本 API から手入力できる。
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.enums import AiOriginEnum, InquirySourceEnum, InquiryStatusEnum
from app.db.models.inquiry import Inquiry

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


class InquiryIn(BaseModel):
    received_at: datetime | None = None
    industry: str | None = None
    company_size: str | None = None
    content_text: str = Field(min_length=1, max_length=10000)
    source_channel: InquirySourceEnum = InquirySourceEnum.web
    ai_origin: AiOriginEnum | None = None
    status: InquiryStatusEnum = InquiryStatusEnum.new


class InquiryOut(InquiryIn):
    id: uuid.UUID


def _row_dict(r: Inquiry) -> dict:
    return {
        "id": r.id,
        "received_at": r.received_at,
        "industry": r.industry,
        "company_size": r.company_size,
        "content_text": r.content_text,
        "source_channel": r.source_channel,
        "ai_origin": r.ai_origin,
        "status": r.status,
    }


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/", response_model=list[InquiryOut])
async def list_inquiries(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    limit: int = 50,
) -> list[InquiryOut]:
    await _set_ctx(session, tenant_id)
    rows = list(
        (
            await session.scalars(
                select(Inquiry)
                .where(Inquiry.tenant_id == tenant_id)
                .order_by(Inquiry.received_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [InquiryOut(**_row_dict(r)) for r in rows]


@router.post("/", response_model=InquiryOut, status_code=201)
async def create_inquiry(
    body: InquiryIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> InquiryOut:
    await _set_ctx(session, tenant_id)
    row = Inquiry(
        tenant_id=tenant_id,
        received_at=body.received_at or datetime.utcnow(),
        industry=body.industry,
        company_size=body.company_size,
        content_text=body.content_text,
        source_channel=body.source_channel,
        ai_origin=body.ai_origin,
        status=body.status,
        raw_payload={"source": "manual"},
    )
    session.add(row)
    await session.flush()
    result = InquiryOut(**_row_dict(row))
    await session.commit()
    return result


class InquiryStatusUpdate(BaseModel):
    status: InquiryStatusEnum


@router.patch("/{inquiry_id}/status", response_model=InquiryOut)
async def update_status(
    inquiry_id: uuid.UUID,
    body: InquiryStatusUpdate,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> InquiryOut:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(Inquiry).where(
                Inquiry.tenant_id == tenant_id, Inquiry.id == inquiry_id
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    row.status = body.status
    await session.flush()
    result = InquiryOut(**_row_dict(row))
    await session.commit()
    return result
