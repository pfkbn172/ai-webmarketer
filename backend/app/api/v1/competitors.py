"""競合ドメイン管理 API。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.competitor import Competitor

router = APIRouter(prefix="/competitors", tags=["competitors"])


class CompetitorIn(BaseModel):
    domain: str = Field(min_length=3, max_length=200)
    brand_name: str | None = None
    rss_url: str | None = None
    is_active: bool = True


class CompetitorOut(CompetitorIn):
    id: uuid.UUID


def _row_dict(r: Competitor) -> dict:
    return {
        "id": r.id,
        "domain": r.domain,
        "brand_name": r.brand_name,
        "rss_url": r.rss_url,
        "is_active": r.is_active,
    }


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/", response_model=list[CompetitorOut])
async def list_competitors(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CompetitorOut]:
    await _set_ctx(session, tenant_id)
    rows = list(
        (
            await session.scalars(
                select(Competitor)
                .where(Competitor.tenant_id == tenant_id)
                .order_by(Competitor.domain)
            )
        ).all()
    )
    return [CompetitorOut(**_row_dict(r)) for r in rows]


@router.post("/", response_model=CompetitorOut, status_code=201)
async def create_competitor(
    body: CompetitorIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> CompetitorOut:
    await _set_ctx(session, tenant_id)
    row = Competitor(tenant_id=tenant_id, **body.model_dump())
    session.add(row)
    try:
        await session.flush()
        result = CompetitorOut(**_row_dict(row))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        # uq_competitors_tenant_domain 違反を想定
        msg = "同じドメインが既に登録されています" if "uq_competitors_tenant_domain" in str(exc) else str(exc)
        raise HTTPException(status_code=400, detail=msg) from None
    return result


@router.put("/{competitor_id}", response_model=CompetitorOut)
async def update_competitor(
    competitor_id: uuid.UUID,
    body: CompetitorIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> CompetitorOut:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(Competitor).where(
                Competitor.tenant_id == tenant_id, Competitor.id == competitor_id
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    try:
        await session.flush()
        result = CompetitorOut(**_row_dict(row))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return result


@router.delete("/{competitor_id}", status_code=204)
async def delete_competitor(
    competitor_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(Competitor).where(
                Competitor.tenant_id == tenant_id, Competitor.id == competitor_id
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    await session.delete(row)
    await session.commit()
