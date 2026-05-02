"""著者プロフィール管理 API。E-E-A-T シグナルとして使用。

仕様書 4.2.2 / Q9: テナントあたり複数著者対応(法律事務所のように複数士業)。
is_primary は同テナント内で最大 1 件(部分一意 INDEX で DB 保証)。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.author_profile import AuthorProfile

router = APIRouter(prefix="/author-profiles", tags=["author_profiles"])


class AuthorProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    job_title: str | None = None
    works_for: str | None = None
    alumni_of: list[str] = []
    credentials: list[str] = []
    expertise: list[str] = []
    publications: list[dict] = []
    speaking_engagements: list[dict] = []
    awards: list[str] = []
    bio_short: str | None = Field(default=None, max_length=200)
    bio_long: str | None = Field(default=None, max_length=2000)
    social_profiles: list[str] = []
    is_primary: bool = False


class AuthorProfileOut(AuthorProfileIn):
    id: uuid.UUID


def _row_dict(r: AuthorProfile) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "job_title": r.job_title,
        "works_for": r.works_for,
        "alumni_of": r.alumni_of or [],
        "credentials": r.credentials or [],
        "expertise": r.expertise or [],
        "publications": r.publications or [],
        "speaking_engagements": r.speaking_engagements or [],
        "awards": r.awards or [],
        "bio_short": r.bio_short,
        "bio_long": r.bio_long,
        "social_profiles": r.social_profiles or [],
        "is_primary": r.is_primary,
    }


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/", response_model=list[AuthorProfileOut])
async def list_authors(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuthorProfileOut]:
    await _set_ctx(session, tenant_id)
    rows = list(
        (
            await session.scalars(
                select(AuthorProfile)
                .where(AuthorProfile.tenant_id == tenant_id)
                .order_by(AuthorProfile.is_primary.desc(), AuthorProfile.created_at)
            )
        ).all()
    )
    return [AuthorProfileOut(**_row_dict(r)) for r in rows]


@router.post("/", response_model=AuthorProfileOut, status_code=201)
async def create_author(
    body: AuthorProfileIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> AuthorProfileOut:
    await _set_ctx(session, tenant_id)
    # is_primary=true の場合、既存の primary を false にする
    if body.is_primary:
        await session.execute(
            text(
                "UPDATE author_profiles SET is_primary = false "
                "WHERE tenant_id = :tid AND is_primary = true"
            ),
            {"tid": str(tenant_id)},
        )
    row = AuthorProfile(tenant_id=tenant_id, **body.model_dump())
    session.add(row)
    try:
        await session.flush()
        result = AuthorProfileOut(**_row_dict(row))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return result


@router.put("/{author_id}", response_model=AuthorProfileOut)
async def update_author(
    author_id: uuid.UUID,
    body: AuthorProfileIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> AuthorProfileOut:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(AuthorProfile).where(
                AuthorProfile.tenant_id == tenant_id, AuthorProfile.id == author_id
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    # is_primary=true に変更する場合、他を false に
    if body.is_primary and not row.is_primary:
        await session.execute(
            text(
                "UPDATE author_profiles SET is_primary = false "
                "WHERE tenant_id = :tid AND is_primary = true AND id <> :id"
            ),
            {"tid": str(tenant_id), "id": str(author_id)},
        )

    for field, value in body.model_dump().items():
        setattr(row, field, value)
    try:
        await session.flush()
        result = AuthorProfileOut(**_row_dict(row))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return result


@router.delete("/{author_id}", status_code=204)
async def delete_author(
    author_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(AuthorProfile).where(
                AuthorProfile.tenant_id == tenant_id, AuthorProfile.id == author_id
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    await session.delete(row)
    await session.commit()
