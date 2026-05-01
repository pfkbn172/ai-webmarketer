"""Google Gemini Adapter(Phase 1 デフォルトプロバイダ)。

implementation_plan 4.3 の方針通り。AI Overviews 用ではなく、月次レポート / ドラフト
生成等の通常 AI 処理に使う。引用モニタの Gemini クライアントとは別物
(collectors/llm_citation/gemini_client.py)。
"""

from collections.abc import AsyncIterator
from typing import Literal

from google import genai
from google.genai import types as gtypes
from pydantic import BaseModel

from app.ai_engine.providers.base import AIProvider
from app.ai_engine.providers.schemas import ProviderError, ProviderResponse, TokenUsage


def _retriable(exc: Exception) -> bool:
    """5xx / Rate limit / Timeout はリトライ対象。"""
    msg = str(exc).lower()
    return any(s in msg for s in ("rate", "timeout", "503", "502", "504"))


class GeminiAdapter(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        response_format: Literal["text", "json"] = "text",
        extra: dict | None = None,
    ) -> ProviderResponse:
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type=(
                "application/json" if response_format == "json" else "text/plain"
            ),
            **(extra or {}),
        )
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model, contents=user_prompt, config=config
            )
        except Exception as exc:
            raise ProviderError(
                str(exc), provider="gemini", retriable=_retriable(exc), cause=exc
            ) from None

        usage = resp.usage_metadata
        return ProviderResponse(
            text=resp.text or "",
            usage=TokenUsage(
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                total_tokens=getattr(usage, "total_token_count", 0) or 0,
            ),
            provider="gemini",
            model=self.model,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
            finish_reason=(
                str(resp.candidates[0].finish_reason)
                if resp.candidates
                else None
            ),
        )

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        extra: dict | None = None,
    ) -> BaseModel:
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
            **(extra or {}),
        )
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model, contents=user_prompt, config=config
            )
        except Exception as exc:
            raise ProviderError(
                str(exc), provider="gemini", retriable=_retriable(exc), cause=exc
            ) from None
        return schema.model_validate_json(resp.text or "{}")

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        extra: dict | None = None,
    ) -> AsyncIterator[str]:
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            **(extra or {}),
        )
        async for chunk in self._client.aio.models.generate_content_stream(
            model=self.model, contents=user_prompt, config=config
        ):
            if chunk.text:
                yield chunk.text

    def count_tokens(self, text: str) -> int:
        try:
            return self._client.models.count_tokens(
                model=self.model, contents=text
            ).total_tokens
        except Exception:
            return max(1, len(text) // 4)
