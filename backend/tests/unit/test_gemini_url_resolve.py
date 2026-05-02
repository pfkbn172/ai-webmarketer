"""Gemini wrapper URL resolution の単体テスト。"""


import httpx
import pytest

from app.collectors.llm_citation.gemini_client import _resolve_wrapper_urls


async def test_non_wrapper_urls_pass_through() -> None:
    out = await _resolve_wrapper_urls(
        ["https://example.com/page"], domain_hints=[]
    )
    assert out == ["https://example.com/page"]


async def test_wrapper_url_uses_domain_hint_when_head_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HEAD/GET が失敗したら domain_hints から合成 URL にフォールバック。"""

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.collectors.llm_citation.gemini_client.httpx.AsyncClient", FakeClient)

    out = await _resolve_wrapper_urls(
        ["https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"],
        domain_hints=["kiseeeen.co.jp"],
    )
    assert out == ["https://kiseeeen.co.jp/"]


async def test_wrapper_url_resolves_via_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HEAD で Location ヘッダが返れば実 URL を採用。"""

    class FakeResp:
        status_code = 302
        headers = {"location": "https://kiseeeen.co.jp/about"}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url):
            return FakeResp()

    monkeypatch.setattr("app.collectors.llm_citation.gemini_client.httpx.AsyncClient", FakeClient)

    out = await _resolve_wrapper_urls(
        ["https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"],
        domain_hints=[],
    )
    assert out == ["https://kiseeeen.co.jp/about"]


async def test_dedup_resolved_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """同じラッパーが 2 回出ても resolved URL は 1 回だけ HEAD し、出力も dedup。"""
    call_count = 0

    class FakeResp:
        status_code = 302
        headers = {"location": "https://kiseeeen.co.jp/x"}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url):
            nonlocal call_count
            call_count += 1
            return FakeResp()

    monkeypatch.setattr("app.collectors.llm_citation.gemini_client.httpx.AsyncClient", FakeClient)

    out = await _resolve_wrapper_urls(
        [
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc",
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc",
        ],
        domain_hints=[],
    )
    assert out == ["https://kiseeeen.co.jp/x"]
    assert call_count == 1  # キャッシュで 1 回のみ
