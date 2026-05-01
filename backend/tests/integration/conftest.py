"""Integration テスト用 fixtures。

実 PostgreSQL に接続して RLS を含めた挙動を検証する。VPS 上の `marketer` DB を直接使い、
テスト後にトランザクションをロールバックして副作用を残さない。

実行: pytest tests/integration -q
CI で実行する場合は別途 PostgreSQL service を立てる必要があるが、Phase 1 では VPS 上での
ローカル実行を前提とする(W1-13 で CI 対応を本格化)。
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings


def _has_postgres() -> bool:
    """PostgreSQL に接続できる環境か(localhost / VPS 上 / .env DSN)。

    CI の GitHub Actions では実 DB が無いのでスキップする目印に使う。
    """
    return os.environ.get("CI") != "true" and "127.0.0.1" in settings.db_dsn


@pytest_asyncio.fixture
async def pg_session() -> AsyncIterator[AsyncSession]:
    """1 テスト 1 トランザクション。最後にロールバックして DB 状態を元に戻す。"""
    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def two_tenants(pg_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """RLS テスト用に 2 つのテナントと、それぞれ 1 件ずつのターゲットクエリを作成。

    fixture の中では `app.tenant_id` を都度 set_config で切り替え。
    INSERT 時の WITH CHECK を通すため、必ず正しい tenant_id を設定してから挿入する。
    """
    a = uuid.uuid4()
    b = uuid.uuid4()
    # tenants の RLS は WITH CHECK で id = current_setting('app.tenant_id') を要求するので、
    # 各 tenant 作成前に該当 id を session 変数に設定する必要がある。
    for tid in (a, b):
        await pg_session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tid)},
        )
        await pg_session.execute(
            text(
                "INSERT INTO tenants (id, name, domain, compliance_type, is_active) "
                "VALUES (:id, :name, :domain, 'general', true)"
            ),
            {"id": str(tid), "name": f"tenant-{tid.hex[:6]}", "domain": "example.test"},
        )
        await pg_session.execute(
            text(
                "INSERT INTO target_queries (tenant_id, query_text) VALUES (:tid, :q)"
            ),
            {"tid": str(tid), "q": f"query-{tid.hex[:6]}"},
        )
    return a, b
