"""マーケティング施策タイムライン API。

ダッシュボードのグラフに「いつ何をしたか」を重ねるためのデータ層。
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.enums import MarketingActionCategoryEnum
from app.db.models.marketing_action import MarketingAction

router = APIRouter(prefix="/marketing-actions", tags=["marketing-actions"])


class MarketingActionIn(BaseModel):
    action_date: date
    category: MarketingActionCategoryEnum = MarketingActionCategoryEnum.other
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class MarketingActionPatch(BaseModel):
    action_date: date | None = None
    category: MarketingActionCategoryEnum | None = None
    title: str | None = None
    description: str | None = None


class MarketingActionOut(MarketingActionIn):
    id: uuid.UUID


def _row(r: MarketingAction) -> MarketingActionOut:
    return MarketingActionOut(
        id=r.id,
        action_date=r.action_date,
        category=r.category,
        title=r.title,
        description=r.description,
    )


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("", response_model=list[MarketingActionOut])
async def list_actions(
    start: date | None = None,
    end: date | None = None,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[MarketingActionOut]:
    """期間フィルタ可能。指定なしなら全件、新しい日付順に返す。"""
    await _set_ctx(session, tenant_id)
    stmt = select(MarketingAction).where(MarketingAction.tenant_id == tenant_id)
    if start is not None:
        stmt = stmt.where(MarketingAction.action_date >= start)
    if end is not None:
        stmt = stmt.where(MarketingAction.action_date <= end)
    stmt = stmt.order_by(MarketingAction.action_date.desc())
    rows = list((await session.scalars(stmt)).all())
    return [_row(r) for r in rows]


@router.post("", response_model=MarketingActionOut, status_code=201)
async def create_action(
    body: MarketingActionIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> MarketingActionOut:
    await _set_ctx(session, tenant_id)
    row = MarketingAction(
        tenant_id=tenant_id,
        action_date=body.action_date,
        category=body.category,
        title=body.title,
        description=body.description,
    )
    session.add(row)
    await session.flush()
    out = _row(row)
    await session.commit()
    return out


@router.patch("/{action_id}", response_model=MarketingActionOut)
async def update_action(
    action_id: uuid.UUID,
    body: MarketingActionPatch,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> MarketingActionOut:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(MarketingAction).where(
                MarketingAction.id == action_id,
                MarketingAction.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    if body.action_date is not None:
        row.action_date = body.action_date
    if body.category is not None:
        row.category = body.category
    if body.title is not None:
        row.title = body.title
    if body.description is not None:
        row.description = body.description
    await session.flush()
    out = _row(row)
    await session.commit()
    return out


@router.delete("/{action_id}", status_code=204)
async def delete_action(
    action_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(MarketingAction).where(
                MarketingAction.id == action_id,
                MarketingAction.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)
