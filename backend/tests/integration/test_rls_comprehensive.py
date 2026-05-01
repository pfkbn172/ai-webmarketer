"""主要テナントテーブルの RLS 網羅テスト。

各テーブルについて:
- テナント A セッションでテナント B のデータが見えないこと
- WITH CHECK により他テナント用の挿入が拒否されること
- app.tenant_id 未設定なら何も見えないこと

W1-05 の test_rls_isolation.py(target_queries 単体)を補強する位置づけ。
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import _has_postgres

pytestmark = pytest.mark.skipif(not _has_postgres(), reason="実 PostgreSQL が必要")


async def _set_ctx(session: AsyncSession, tid: uuid.UUID | None) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tid) if tid else ""},
    )


async def test_competitors_isolated(
    pg_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = two_tenants
    # A コンテキストで A の競合を 1 件作成
    await _set_ctx(pg_session, a)
    await pg_session.execute(
        text("INSERT INTO competitors (tenant_id, domain) VALUES (:tid, :d)"),
        {"tid": str(a), "d": "rival-a.com"},
    )
    # B コンテキストで B の競合を 2 件作成
    await _set_ctx(pg_session, b)
    for d in ("rival-b1.com", "rival-b2.com"):
        await pg_session.execute(
            text("INSERT INTO competitors (tenant_id, domain) VALUES (:tid, :d)"),
            {"tid": str(b), "d": d},
        )

    # A から見える件数
    await _set_ctx(pg_session, a)
    rows = (await pg_session.execute(text("SELECT COUNT(*) FROM competitors"))).scalar_one()
    assert rows == 1
    # B から見える件数
    await _set_ctx(pg_session, b)
    rows = (await pg_session.execute(text("SELECT COUNT(*) FROM competitors"))).scalar_one()
    assert rows == 2


async def test_with_check_blocks_cross_tenant_insert(
    pg_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """A コンテキストで B の tenant_id を持つ行を挿入しようとすると WITH CHECK で失敗。"""
    a, b = two_tenants
    await _set_ctx(pg_session, a)
    with pytest.raises(DBAPIError):  # RLS WITH CHECK 違反は driver 例外として浮上
        await pg_session.execute(
            text("INSERT INTO competitors (tenant_id, domain) VALUES (:tid, :d)"),
            {"tid": str(b), "d": "rival.com"},
        )
    await pg_session.rollback()


async def test_multiple_tables_invisible_without_setting(
    pg_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, _ = two_tenants
    await _set_ctx(pg_session, a)
    await pg_session.execute(
        text("INSERT INTO competitors (tenant_id, domain) VALUES (:tid, :d)"),
        {"tid": str(a), "d": "rival.com"},
    )
    # 各テーブルでも RESET 後は何も見えない
    await pg_session.execute(text("RESET app.tenant_id"))
    for table in [
        "tenants",
        "target_queries",
        "competitors",
        "author_profiles",
        "contents",
        "citation_logs",
        "inquiries",
        "reports",
        "kpi_logs",
        "ai_provider_configs",
        "tenant_credentials",
        "schema_audit_logs",
        "gsc_query_metrics",
        "ga4_daily_metrics",
    ]:
        rows = (await pg_session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()
        assert rows == 0, f"{table} は未設定状態で {rows} 行見える(0 でなければならない)"


async def test_author_profile_primary_partial_unique(
    pg_session: AsyncSession, two_tenants: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """uq_author_profiles_primary 部分一意 INDEX:
    同一テナント内で is_primary=true は 1 件まで。複数テナントなら各 1 件可。

    SAVEPOINT を使って unique 違反による rollback で外側のトランザクションを
    巻き込まないようにする。
    """
    a, b = two_tenants

    # A に primary を 1 件挿入(これは成功)
    await _set_ctx(pg_session, a)
    await pg_session.execute(
        text(
            "INSERT INTO author_profiles (tenant_id, name, is_primary) "
            "VALUES (:tid, 'A1', true)"
        ),
        {"tid": str(a)},
    )

    # 2 件目の primary を SAVEPOINT 内で試す → 失敗 → savepoint だけロールバック
    sp = await pg_session.begin_nested()
    with pytest.raises(IntegrityError):
        await pg_session.execute(
            text(
                "INSERT INTO author_profiles (tenant_id, name, is_primary) "
                "VALUES (:tid, 'A2', true)"
            ),
            {"tid": str(a)},
        )
    await sp.rollback()

    # 同テナントに non-primary は OK
    await pg_session.execute(
        text(
            "INSERT INTO author_profiles (tenant_id, name, is_primary) "
            "VALUES (:tid, 'A_sub', false)"
        ),
        {"tid": str(a)},
    )

    # 別テナント B にも primary 1 件は OK
    await _set_ctx(pg_session, b)
    await pg_session.execute(
        text(
            "INSERT INTO author_profiles (tenant_id, name, is_primary) "
            "VALUES (:tid, 'B1', true)"
        ),
        {"tid": str(b)},
    )
