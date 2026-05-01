"""テスト用 Mock Adapter。

実 LLM を呼ばず固定文字列を返す。
ユースケース層のテストで使う。
"""

from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel

from app.ai_engine.providers.base import AIProvider
from app.ai_engine.providers.schemas import ProviderResponse, TokenUsage


class MockAdapter(AIProvider):
    name = "mock"

    def __init__(self, *, fixed_text: str = "mock response", model: str = "mock-1") -> None:
        self.model = model
        self._fixed = fixed_text

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
        return ProviderResponse(
            text=self._fixed,
            usage=TokenUsage(input_tokens=10, output_tokens=10, total_tokens=20),
            provider=self.name,
            model=self.model,
            raw_response=None,
            finish_reason="stop",
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
        # 各フィールドにダミー値を埋める
        from typing import get_origin

        dummy: dict = {}
        for name, field in schema.model_fields.items():
            ann = field.annotation
            origin = get_origin(ann)
            if ann is str or origin is str:
                dummy[name] = "mock"
            elif ann is int:
                dummy[name] = 0
            elif ann is float:
                dummy[name] = 0.0
            elif ann is bool:
                dummy[name] = False
            elif origin is list:
                dummy[name] = []
            else:
                dummy[name] = None
        return schema.model_validate(dummy)

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        extra: dict | None = None,
    ) -> AsyncIterator[str]:
        for chunk in self._fixed.split():
            yield chunk + " "

    def count_tokens(self, text: str) -> int:
        # 4 文字 1 トークン近似
        return max(1, len(text) // 4)
