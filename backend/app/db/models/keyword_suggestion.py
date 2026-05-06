"""Google/Bing サジェスト・競合見出しから収集したキーワード候補の生データ。

aggregate_keyword_universe ジョブで keyword_universe に集約される。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class KeywordSuggestion(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "keyword_suggestions"
    __table_args__ = (
        Index("ix_kws_tenant_fetched", "tenant_id", "fetched_at"),
        Index("ix_kws_tenant_source", "tenant_id", "source"),
        Index("ix_kws_tenant_seed_derived", "tenant_id", "seed_keyword", "derived_keyword"),
    )

    # 'google_suggest' | 'bing_suggest' | 'competitor_h1' | 'competitor_h2' | 'competitor_h3' | 'competitor_title'
    source: Mapped[str] = mapped_column(Text, nullable=False)
    seed_keyword: Mapped[str | None] = mapped_column(Text)
    derived_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
