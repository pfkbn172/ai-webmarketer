"""Google AI Overviews を SerpApi 経由で取得する引用モニタクライアント。

仕様書 16: SerpApi / DataForSEO / 自前スクレイピングを切替できる抽象構造を将来導入
予定。Phase 1 は SerpApi のみ。
"""

import re

import httpx

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)
URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")


class AIOverviewsCitationClient:
    """SerpApi の `engine=google_ai_overview` または `google` の ai_overview 結果を使う。"""

    def __init__(self, api_key: str, hl: str = "ja", gl: str = "jp") -> None:
        self._api_key = api_key
        self._hl = hl
        self._gl = gl

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(httpx.HTTPError,))
    async def probe(self, query_text: str) -> CitationProbeResult:
        params = {
            "engine": "google",
            "q": query_text,
            "hl": self._hl,
            "gl": self._gl,
            "api_key": self._api_key,
            "output": "json",
        }
        async with httpx.AsyncClient(timeout=60.0) as http:
            resp = await http.get("https://serpapi.com/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        ai_overview = data.get("ai_overview") or {}
        text_blocks = ai_overview.get("text_blocks") or []
        text = "\n".join(
            blk.get("snippet") or blk.get("text") or ""
            for blk in text_blocks
            if isinstance(blk, dict)
        )

        urls: list[str] = []
        for ref in ai_overview.get("references", []) or []:
            u = ref.get("link") or ref.get("url")
            if u:
                urls.append(u)
        if not urls:
            urls = URL_RE.findall(text)
        urls = list(dict.fromkeys(urls))

        log.info("aio_probe_done", query=query_text[:60], n_urls=len(urls))
        return CitationProbeResult(
            llm_provider=LLMProviderEnum.aio,
            query_text=query_text,
            response_text=text,
            cited_urls=urls,
            raw_response=ai_overview,
        )
