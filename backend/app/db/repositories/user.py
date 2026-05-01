"""User リポジトリ。users テーブルは RLS 対象外(管理者横断テーブル)のため、
BaseRepository の tenant_id 必須化パターンには従わない。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self.session.scalars(stmt)).one_or_none()

    async def get(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await self.session.scalars(stmt)).one_or_none()

    async def list_tenants_for(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        from app.db.models.user_tenant import UserTenant
        stmt = select(UserTenant.tenant_id).where(UserTenant.user_id == user_id)
        return list((await self.session.scalars(stmt)).all())
