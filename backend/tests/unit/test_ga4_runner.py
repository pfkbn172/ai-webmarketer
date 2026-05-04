"""GA4 ランナーのモック化単体テスト。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.collectors.ga4 import runner as ga4_runner
from app.collectors.ga4.client import Ga4DailyRow
from app.collectors.google_oauth import CredentialsNotFoundError


@pytest.fixture
def fake_session() -> MagicMock:
    s = MagicMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


async def test_skipped_when_no_credentials(
    fake_session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid as _uuid

    async def raise_not_found(*args, **kwargs):
        raise CredentialsNotFoundError("missing")

    monkeypatch.setattr(ga4_runner, "load_google_credentials", raise_not_found)

    n = await ga4_runner.run_for_tenant(fake_session, _uuid.uuid4(), property_id="123")
    assert n == 0


async def test_upsert_called_with_rows(
    fake_session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid as _uuid

    async def fake_load(*args, **kwargs):
        return MagicMock()

    fake_rows = [
        Ga4DailyRow(
            date=date(2026, 5, 1),
            sessions=100,
            users=80,
            bounce_rate=0.45,
            conversions=2,
            organic_sessions=60,
        ),
    ]
    fake_client = MagicMock()
    fake_client.daily_metrics = AsyncMock(return_value=fake_rows)
    fake_client.ai_referrals = AsyncMock(return_value=[])
    fake_client.page_metrics = AsyncMock(return_value=[])

    monkeypatch.setattr(ga4_runner, "load_google_credentials", fake_load)
    monkeypatch.setattr(ga4_runner, "Ga4Client", lambda *a, **kw: fake_client)

    n = await ga4_runner.run_for_tenant(fake_session, _uuid.uuid4(), property_id="123")
    assert n == 1
    assert fake_session.execute.await_count >= 2
