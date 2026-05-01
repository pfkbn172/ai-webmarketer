"""ターゲットクエリ管理 API。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.target_query import TargetQuery

router = APIRouter(prefix="/target-queries", tags=["target_queries"])


class TargetQueryIn(BaseModel):
    query_text: str
    cluster_id: str | None = None
    priority: int = 3
    expected_conversion: int = 3
    search_intent: str | None = None
    is_active: bool = True


class TargetQueryOut(TargetQueryIn):
    id: uuid.UUID


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/", response_model=list[TargetQueryOut])
async def list_queries(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[TargetQueryOut]:
    await _set_ctx(session, tenant_id)
    rows = list(
        (
            await session.scalars(
                select(TargetQuery)
                .where(TargetQuery.tenant_id == tenant_id)
                .order_by(TargetQuery.created_at.desc())
            )
        ).all()
    )
    return [TargetQueryOut(**_row_dict(r)) for r in rows]


@router.post("/", response_model=TargetQueryOut, status_code=201)
async def create_query(
    body: TargetQueryIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> TargetQueryOut:
    await _set_ctx(session, tenant_id)
    row = TargetQuery(
        tenant_id=tenant_id,
        query_text=body.query_text,
        cluster_id=body.cluster_id,
        priority=body.priority,
        expected_conversion=body.expected_conversion,
        search_intent=body.search_intent,
        is_active=body.is_active,
    )
    session.add(row)
    try:
        await session.flush()
        # commit 前にレスポンス用の値を確定する(commit 後は新トランザクションで
        # RLS の app.tenant_id が消えるため refresh が失敗する)
        result = TargetQueryOut(**_row_dict(row))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return result


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(TargetQuery).where(
                TargetQuery.tenant_id == tenant_id, TargetQuery.id == query_id
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    await session.delete(row)
    await session.commit()


def _row_dict(r: TargetQuery) -> dict:
    return {
        "id": r.id,
        "query_text": r.query_text,
        "cluster_id": r.cluster_id,
        "priority": r.priority,
        "expected_conversion": r.expected_conversion,
        "search_intent": r.search_intent,
        "is_active": r.is_active,
    }
