"""Repository パターンの基底クラス。

設計指針 4.1 / 4.2:
- API・サービス層から直接 ORM を呼ばず、Repository を経由する
- tenant_id を必須引数化し、内部で `WHERE tenant_id = :tid` を必ず付加
- これは RLS の二重防御(アプリ層 + DB 層)

サブクラスは __model__ にテーブル ORM クラスを設定し、共通の取得・作成・削除メソッドを継承する。
複雑なクエリは各サブクラスで個別メソッドとして実装する。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class BaseRepository[ModelT: Base]:
    """テナント所属テーブル用の基底 Repository。

    使い方:
        class TargetQueryRepository(BaseRepository[TargetQuery]):
            __model__ = TargetQuery

            async def find_active(self, tenant_id: UUID) -> list[TargetQuery]:
                stmt = self._tenant_query(tenant_id).where(TargetQuery.is_active.is_(True))
                return list((await self.session.scalars(stmt)).all())
    """

    __model__: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _tenant_query(self, tenant_id: UUID):
        return select(self.__model__).where(self.__model__.tenant_id == tenant_id)  # type: ignore[attr-defined]

    async def get(self, tenant_id: UUID, id_: UUID) -> ModelT | None:
        stmt = self._tenant_query(tenant_id).where(self.__model__.id == id_)  # type: ignore[attr-defined]
        return (await self.session.scalars(stmt)).one_or_none()

    async def list(self, tenant_id: UUID, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = self._tenant_query(tenant_id).limit(limit).offset(offset)
        return list((await self.session.scalars(stmt)).all())

    async def add(self, instance: ModelT) -> ModelT:
        """追加対象オブジェクトに tenant_id が既に設定されていることを呼び出し元が保証する。"""
        if getattr(instance, "tenant_id", None) is None:
            raise ValueError(
                f"{type(instance).__name__}.tenant_id is required before add()"
            )
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, tenant_id: UUID, id_: UUID) -> int:
        stmt = (
            delete(self.__model__)
            .where(self.__model__.tenant_id == tenant_id)  # type: ignore[attr-defined]
            .where(self.__model__.id == id_)  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0
