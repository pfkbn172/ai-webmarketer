"""引用モニタ用の共通型。"""

from dataclasses import dataclass, field

from app.db.models.enums import LLMProviderEnum


@dataclass(frozen=True, slots=True)
class CitationProbeResult:
    """1 LLM × 1 クエリの問い合わせ結果。"""

    llm_provider: LLMProviderEnum
    query_text: str
    response_text: str
    cited_urls: list[str] = field(default_factory=list)
    raw_response: dict | None = None
