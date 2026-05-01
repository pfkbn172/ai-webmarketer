"""AIProvider 抽象基底クラス(implementation_plan 4.1)。

各 Adapter の追加で必要な変更を 3 ステップに留める設計:
1. providers/<new>_adapter.py を実装
2. factory.py の _registry に 1 行追加
3. ai_provider enum は Phase 1 で全プロバイダ登録済(追加不要)

ユースケース層は Provider を直接知らない。Factory 経由で取得する。
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel

from app.ai_engine.providers.schemas import ProviderResponse


class AIProvider(ABC):
    """すべての Provider Adapter が継承する基底クラス。"""

    name: str  # 'gemini' | 'claude' | 'openai' | 'perplexity'
    model: str

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        response_format: Literal["text", "json"] = "text",
        extra: dict | None = None,
    ) -> ProviderResponse: ...

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        extra: dict | None = None,
    ) -> BaseModel: ...

    @abstractmethod
    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        extra: dict | None = None,
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    def count_tokens(self, text: str) -> int: ...
