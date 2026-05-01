"""RLS によるマルチテナント分離の最小確認。

W1-13 で全テーブル × 各種操作の網羅テストを追加する予定。
本ファイルでは「RLS が動いていることが分かる最小例」を 1 ケースだけ確認する。
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import _has_postgres

pytestmark = pytest.mark.skipif(not _has_postgres(), reason="実 PostgreSQL が必要")


async def test_target_queries_isolated_by_rls(
    pg_session: AsyncSession,
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    a, b = two_tenants

    # テナント A のセッション設定
    await pg_session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(a)},
    )
    rows = (await pg_session.execute(text("SELECT tenant_id FROM target_queries"))).all()
    assert len(rows) == 1
    assert rows[0][0] == a

    # テナント B に切替
    await pg_session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(b)},
    )
    rows = (await pg_session.execute(text("SELECT tenant_id FROM target_queries"))).all()
    assert len(rows) == 1
    assert rows[0][0] == b

    # 設定なしだと何も見えない
    await pg_session.execute(text("RESET app.tenant_id"))
    rows = (await pg_session.execute(text("SELECT tenant_id FROM target_queries"))).all()
    assert rows == []
