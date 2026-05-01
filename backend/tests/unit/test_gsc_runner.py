"""GSC ランナーのモック化単体テスト。

Google API クライアントをモック化し、ジョブ全体のフロー(認証情報なし → skipped、
正常 → success + メトリクス保存)を確認する。実 GSC への接続テストは Phase 1 の
本番デプロイ後に手動実施。
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.collectors.google_oauth import CredentialsNotFoundError
from app.collectors.gsc import runner as gsc_runner
from app.collectors.gsc.client import GscRow


@pytest.fixture
def fake_session() -> MagicMock:
    s = MagicMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


async def test_run_for_tenant_returns_zero_when_credentials_missing(
    fake_session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """認証情報未登録なら status=skipped で 0 行返す。"""
    import uuid as _uuid

    async def raise_not_found(*args, **kwargs):
        raise CredentialsNotFoundError("not registered")

    monkeypatch.setattr(gsc_runner, "load_google_credentials", raise_not_found)

    n = await gsc_runner.run_for_tenant(
        fake_session, _uuid.uuid4(), site_url="sc-domain:example.com"
    )
    assert n == 0


async def test_run_for_tenant_upserts_metrics(
    fake_session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """正常系: GscClient.query_metrics の戻り値を upsert に流す。"""
    import uuid as _uuid

    async def fake_load(*args, **kwargs):
        return MagicMock()

    fake_rows = [
        GscRow(
            date=date(2026, 5, 1),
            query_text="kiseeeen",
            page=None,
            clicks=10,
            impressions=100,
            ctr=0.1,
            position=2.5,
        ),
        GscRow(
            date=date(2026, 5, 1),
            query_text="ウェブマーケター",
            page=None,
            clicks=3,
            impressions=50,
            ctr=0.06,
            position=5.0,
        ),
    ]

    fake_client = MagicMock()
    fake_client.query_metrics = AsyncMock(return_value=fake_rows)

    monkeypatch.setattr(gsc_runner, "load_google_credentials", fake_load)
    monkeypatch.setattr(gsc_runner, "GscClient", lambda *a, **kw: fake_client)

    n = await gsc_runner.run_for_tenant(
        fake_session, _uuid.uuid4(), site_url="sc-domain:example.com"
    )
    assert n == 2
    # set_config + insert の 2 回は最低呼ばれる
    assert fake_session.execute.await_count >= 2
