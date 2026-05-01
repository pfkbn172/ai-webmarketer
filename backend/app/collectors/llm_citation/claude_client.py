"""Claude(Anthropic)を web_search ツール付きで呼ぶ引用モニタクライアント。"""

import re

from anthropic import AsyncAnthropic

from app.collectors.llm_citation._types import CitationProbeResult
from app.db.models.enums import LLMProviderEnum
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)
URL_RE = re.compile(r"https?://[^\s\)\]\>\}]+")


class ClaudeCitationClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-7") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(Exception,))
    async def probe(self, query_text: str) -> CitationProbeResult:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            messages=[{"role": "user", "content": query_text}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
        text_parts: list[str] = []
        urls: list[str] = []
        for block in resp.content:
            kind = getattr(block, "type", None)
            if kind == "text":
                text_parts.append(getattr(block, "text", ""))
                for cite in getattr(block, "citations", []) or []:
                    u = getattr(cite, "url", None)
                    if u:
                        urls.append(u)
            elif kind == "web_search_tool_result":
                for r in getattr(block, "content", []) or []:
                    u = getattr(r, "url", None)
                    if u:
                        urls.append(u)

        text = "\n".join(text_parts)
        if not urls:
            urls = URL_RE.findall(text)
        urls = list(dict.fromkeys(urls))
        log.info("claude_probe_done", query=query_text[:60], n_urls=len(urls))
        return CitationProbeResult(
            llm_provider=LLMProviderEnum.claude,
            query_text=query_text,
            response_text=text,
            cited_urls=urls,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )
