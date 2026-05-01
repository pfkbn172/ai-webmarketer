import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin
from app.db.models.enums import LLMProviderEnum


class CitationLog(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "citation_logs"
    __table_args__ = (
        Index("ix_citation_logs_tenant_query_date", "tenant_id", "query_id", "query_date"),
    )

    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("target_queries.id", ondelete="CASCADE"),
        nullable=False,
    )
    llm_provider: Mapped[LLMProviderEnum] = mapped_column(
        Enum(LLMProviderEnum, name="llm_provider", native_enum=True, create_type=False),
        nullable=False,
    )
    query_date: Mapped[date] = mapped_column(Date, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text)
    cited_urls: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    self_cited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    competitor_cited: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
