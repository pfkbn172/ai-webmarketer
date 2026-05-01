"""Gemini を Web grounding 付きで呼ぶ引用モニタクライアント。

仕様書 6.3: AI 処理用 Gemini と引用モニタ用 Gemini は別 API キーで分離可能。
本ファイルは抽象レイヤを通さず、ハードコードで grounding を使う。
"""

import re

from google import genai
from google.genai import types as gtypes

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)
URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")


class GeminiCitationClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(Exception,))
    async def probe(self, query_text: str) -> CitationProbeResult:
        config = gtypes.GenerateContentConfig(
            tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=query_text, config=config
        )
        text = resp.text or ""
        urls: list[str] = []
        # grounding_metadata の web_search_queries / grounding_chunks から URL 抽出
        for cand in (resp.candidates or []):
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for chunk in (getattr(gm, "grounding_chunks", []) or []):
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    urls.append(web.uri)
        if not urls:
            urls = URL_RE.findall(text)
        urls = list(dict.fromkeys(urls))
        log.info("gemini_probe_done", query=query_text[:60], n_urls=len(urls))
        return CitationProbeResult(
            llm_provider=LLMProviderEnum.gemini,
            query_text=query_text,
            response_text=text,
            cited_urls=urls,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )
