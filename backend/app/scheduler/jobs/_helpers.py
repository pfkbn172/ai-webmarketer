"""ジョブから DB セッション + 全テナント走査を行うヘルパー。"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings


@asynccontextmanager
async def make_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


def active_tenant_ids() -> list[uuid.UUID]:
    """環境変数 MARKETER_ACTIVE_TENANT_IDS から実行対象テナントを取り出す。

    Phase 1 自社のみ(1 件)を想定。空文字なら空リスト = 何もしない。
    Phase 2 以降でマルチテナント本格化したら DB 経由(BYPASSRLS ロール経由)に置換する。
    """
    raw = settings.active_tenant_ids.strip()
    if not raw:
        return []
    out: list[uuid.UUID] = []
    for token in raw.split(","):
        t = token.strip()
        if not t:
            continue
        try:
            out.append(uuid.UUID(t))
        except ValueError:
            continue
    return out
