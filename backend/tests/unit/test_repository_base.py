"""BaseRepository のテナント分離挙動を、in-memory SQLite で確認するユニットテスト。

実 DB(PostgreSQL + RLS)による分離テストは W1-13 の integration テストで実施。
ここではアプリ層の WHERE tenant_id 強制と add() 時の必須チェックだけを検証する。
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import String, Uuid

from app.db.repositories.base import BaseRepository


class _TestBase(DeclarativeBase):
    """Dummy 用の独立した Base。本番 metadata を汚染しない。"""


# --- テスト専用ダミーモデル ---
class _DummyItem(_TestBase):
    __tablename__ = "_test_dummy_item"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class _DummyRepo(BaseRepository[_DummyItem]):
    __model__ = _DummyItem


@pytest.fixture
async def session() -> AsyncSession:
    """SQLite in-memory に Dummy テーブルだけを作る。

    Base.metadata 全体を create_all すると本番 ORM の JSONB / PGUUID 等が
    SQLite で render できずエラーになる。Dummy のテーブルだけ明示作成する。
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_DummyItem.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_list_filters_by_tenant_id(session: AsyncSession) -> None:
    t_a = uuid.uuid4()
    t_b = uuid.uuid4()
    repo = _DummyRepo(session)

    await repo.add(_DummyItem(tenant_id=t_a, name="a1"))
    await repo.add(_DummyItem(tenant_id=t_a, name="a2"))
    await repo.add(_DummyItem(tenant_id=t_b, name="b1"))
    await session.commit()

    a_items = await repo.list(t_a)
    b_items = await repo.list(t_b)
    assert {i.name for i in a_items} == {"a1", "a2"}
    assert {i.name for i in b_items} == {"b1"}


async def test_get_returns_none_for_other_tenant(session: AsyncSession) -> None:
    t_a = uuid.uuid4()
    t_b = uuid.uuid4()
    repo = _DummyRepo(session)
    item = await repo.add(_DummyItem(tenant_id=t_a, name="x"))
    await session.commit()

    assert await repo.get(t_a, item.id) is not None
    assert await repo.get(t_b, item.id) is None  # 他テナントから見えない


async def test_add_without_tenant_id_raises(session: AsyncSession) -> None:
    repo = _DummyRepo(session)
    bad = _DummyItem(name="no-tenant")  # tenant_id 未設定
    with pytest.raises(ValueError, match="tenant_id is required"):
        await repo.add(bad)


async def test_delete_only_targets_own_tenant(session: AsyncSession) -> None:
    t_a = uuid.uuid4()
    t_b = uuid.uuid4()
    repo = _DummyRepo(session)
    item = await repo.add(_DummyItem(tenant_id=t_a, name="x"))
    await session.commit()

    # 他テナントから消そうとしても 0 件
    assert await repo.delete(t_b, item.id) == 0
    assert await repo.get(t_a, item.id) is not None

    # 正しいテナントなら消せる
    assert await repo.delete(t_a, item.id) == 1
    assert await repo.get(t_a, item.id) is None
