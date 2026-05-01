from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.settings import settings


class Base(DeclarativeBase):
    """全 ORM モデルの基底クラス。Alembic autogenerate で参照される。"""


engine = create_async_engine(
    settings.db_dsn,
    pool_size=settings.db_pool_size,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends で使うセッションプロバイダ。

    W1-04 で TenantContext と組み合わせて `SET LOCAL app.tenant_id` を発行する責務を追加する。
    現状は素の AsyncSession のみ。
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
