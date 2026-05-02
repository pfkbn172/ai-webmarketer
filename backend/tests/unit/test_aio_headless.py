"""AIOverviewsHeadlessClient の単体テスト(Playwright をモック化)。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.collectors.llm_citation import aio_headless_client as mod
from app.collectors.llm_citation.aio_headless_client import (
    AIOverviewsHeadlessClient,
    _extract_aio,
)


async def test_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """start_session() で chromium を起動、close_session() で破棄する。"""

    fake_browser = AsyncMock()
    fake_browser.close = AsyncMock()
    fake_chromium = MagicMock()
    fake_chromium.launch = AsyncMock(return_value=fake_browser)
    fake_pw = MagicMock()
    fake_pw.chromium = fake_chromium
    fake_pw.stop = AsyncMock()
    fake_context = AsyncMock()
    fake_context.add_init_script = AsyncMock()
    fake_context.close = AsyncMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)

    async def fake_start():
        return fake_pw

    fake_async_pw = MagicMock()
    fake_async_pw.start = fake_start
    monkeypatch.setattr(mod, "async_playwright", lambda: fake_async_pw)

    client = AIOverviewsHeadlessClient()
    await client.start_session()
    fake_chromium.launch.assert_called_once()
    fake_browser.new_context.assert_called_once()
    fake_context.add_init_script.assert_called_once()

    await client.close_session()
    fake_context.close.assert_awaited_once()
    fake_browser.close.assert_awaited_once()


async def test_extract_aio_returns_empty_when_no_block() -> None:
    """AIO ブロックが見つからない場合は ('', []) を返す。"""

    page = MagicMock()
    locator = MagicMock()
    locator.first = locator
    locator.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=locator)

    text, urls = await _extract_aio(page)
    assert text == ""
    assert urls == []


async def test_extract_aio_extracts_text_and_urls() -> None:
    """AIO ブロックがある場合、inner_text と anchor href を取得する。"""

    block = MagicMock()
    block.count = AsyncMock(return_value=1)
    block.inner_text = AsyncMock(return_value="Some AI overview text")

    anchors = MagicMock()
    anchors.count = AsyncMock(return_value=2)

    def make_anchor(url: str):
        a = MagicMock()
        a.get_attribute = AsyncMock(return_value=url)
        return a

    anchors.nth = MagicMock(
        side_effect=[
            make_anchor("https://example.com/a"),
            make_anchor("/url?q=https://kiseeeen.co.jp/about&sa=U"),
        ]
    )

    block.locator = MagicMock(return_value=anchors)

    page = MagicMock()
    # selectors のうち最初のものでヒットさせる
    page.locator = MagicMock(return_value=MagicMock(first=block))

    text, urls = await _extract_aio(page)
    assert text == "Some AI overview text"
    assert "https://example.com/a" in urls
    assert "https://kiseeeen.co.jp/about" in urls
