"""Perplexity API クライアント。OpenAI 互換 API。"""

import re

import httpx

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)
URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")

API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityCitationClient:
    def __init__(self, api_key: str, model: str = "sonar") -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._model = model

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(httpx.HTTPError,))
    async def probe(self, query_text: str) -> CitationProbeResult:
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": query_text}],
        }
        async with httpx.AsyncClient(timeout=60.0) as http:
            resp = await http.post(API_URL, headers=self._headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        # Perplexity の response には citations[] フィールドが付くことが多い
        urls: list[str] = list(data.get("citations", []) or [])
        if not urls:
            urls = URL_RE.findall(text)
        urls = list(dict.fromkeys(urls))
        log.info("perplexity_probe_done", query=query_text[:60], n_urls=len(urls))
        return CitationProbeResult(
            llm_provider=LLMProviderEnum.perplexity,
            query_text=query_text,
            response_text=text,
            cited_urls=urls,
            raw_response=data,
        )
