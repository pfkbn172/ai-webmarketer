"""ChatGPT(OpenAI)を Web 検索ツール付きで呼ぶ引用モニタクライアント。

OpenAI Responses API + web_search tool を使う(gpt-4o + web_search_preview)。
"""

import re

from openai import AsyncOpenAI

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)

URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")


class ChatGPTCitationClient:
    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(Exception,))
    async def probe(self, query_text: str) -> CitationProbeResult:
        """クエリを Web 検索付き ChatGPT に投げて回答 + 引用 URL を抽出。"""
        resp = await self._client.responses.create(
            model=self._model,
            input=query_text,
            tools=[{"type": "web_search_preview"}],
        )
        text = resp.output_text or ""
        urls = _extract_urls_from_response(resp, text)
        log.info("chatgpt_probe_done", query=query_text[:60], n_urls=len(urls))
        return CitationProbeResult(
            llm_provider=LLMProviderEnum.chatgpt,
            query_text=query_text,
            response_text=text,
            cited_urls=urls,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )


def _extract_urls_from_response(resp, fallback_text: str) -> list[str]:
    urls: list[str] = []
    for item in getattr(resp, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            for ann in getattr(content, "annotations", []) or []:
                u = getattr(ann, "url", None)
                if u:
                    urls.append(u)
    if not urls:
        urls = URL_RE.findall(fallback_text)
    return list(dict.fromkeys(urls))  # 重複除去、順序保持
