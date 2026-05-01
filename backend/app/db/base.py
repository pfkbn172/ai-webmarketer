"""DB 接続管理。

責務:
- async engine と session factory の提供
- リクエストごとの session 配布(get_db_session)
- リクエストごとに `SET LOCAL app.tenant_id = '<uuid>'` を発行(RLS 連携、W1-05 で全テーブルに RLS 設定)

TenantContext.tenant_id が None のリクエスト(認証前 / public エンドポイント)では
SET LOCAL を発行しないため、RLS ポリシーの `current_setting('app.tenant_id', true)::uuid`
は NULL を返し、テナントテーブルへの参照はすべて拒否される(意図通り)。
"""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.auth.tenant_context import get_tenant_id
from app.settings import settings


class Base(DeclarativeBase):
    """全 ORM モデルの基底クラス。Alembic autogenerate で参照される。"""


def _make_engine():
    return create_async_engine(
        settings.db_dsn,
        pool_size=settings.db_pool_size,
        pool_pre_ping=True,
        future=True,
    )


engine = _make_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def reset_engine() -> None:
    """テストでイベントループ切替時に engine を作り直す用。本番では通常使わない。"""
    global engine, SessionLocal  # noqa: PLW0603
    await engine.dispose()
    engine = _make_engine()
    SessionLocal = async_sessionmaker(
        bind=engine, expire_on_commit=False, class_=AsyncSession
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends 用。

    トランザクション境界はリクエスト単位。エンドポイント側が明示的に commit() を呼ばない
    場合は finally で rollback されるため、書き込みのある API は明示的に commit すること
    (Repository / サービス層で session.commit() を呼ぶ慣習にする)。

    SessionLocal はモジュール変数を毎回 lookup する(reset_engine 後の再作成に追従)。
    """
    session_factory = globals()["SessionLocal"]
    async with session_factory() as session:
        try:
            await _apply_tenant_setting(session)
            yield session
        except Exception:
            await session.rollback()
            raise


async def _apply_tenant_setting(session: AsyncSession) -> None:
    """contextvar の tenant_id を SET LOCAL でセッションに反映。

    SET LOCAL はトランザクション終了で自動破棄される。`SELECT set_config(...)` を使い、
    第3引数 true で「LOCAL」相当を指定。バインドパラメータが効くため SQL インジェクション安全。
    """
    tid = get_tenant_id()
    if tid is None:
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tid)},
    )
