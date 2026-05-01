"""テナント関連 API(Phase 1: 自分が所属するテナント一覧 + 切替)。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user
from app.db.base import get_db_session
from app.db.models.tenant import Tenant
from app.db.repositories.user import UserRepository

router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None
    domain: str


@router.get("/me", response_model=list[TenantOut])
async def my_tenants(
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantOut]:
    repo = UserRepository(session)
    tids = await repo.list_tenants_for(user_id)
    if not tids:
        return []
    out: list[TenantOut] = []
    for tid in tids:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tid)},
        )
        t = (await session.scalars(select(Tenant).where(Tenant.id == tid))).one_or_none()
        if t:
            out.append(
                TenantOut(id=t.id, name=t.name, industry=t.industry, domain=t.domain)
            )
    return out


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantOut:
    repo = UserRepository(session)
    if tenant_id not in await repo.list_tenants_for(user_id):
        raise HTTPException(status_code=403, detail="not allowed")
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    t = (await session.scalars(select(Tenant).where(Tenant.id == tenant_id))).one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="not found")
    return TenantOut(id=t.id, name=t.name, industry=t.industry, domain=t.domain)
