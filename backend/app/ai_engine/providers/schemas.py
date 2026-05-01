"""AI Provider 抽象レイヤの共通データ型(implementation_plan 4.1)。"""

from typing import Any

from pydantic import BaseModel


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ProviderResponse(BaseModel):
    text: str
    usage: TokenUsage
    provider: str
    model: str
    raw_response: dict[str, Any] | None = None
    finish_reason: str | None = None


class ProviderError(Exception):
    """Provider 共通の呼び出しエラー。retriable フラグで上位がリトライ判断。"""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retriable: bool = False,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable
        self.cause = cause
