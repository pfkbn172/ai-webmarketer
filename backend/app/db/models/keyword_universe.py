"""集計済みキーワード辞書。

GSC 実績・サジェスト派生数・競合カバー・LLM 引用率を統合し、
priority_score を付与した「対策候補キーワード」のマスター。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, UpdatedTimestampsMixin


class KeywordUniverse(Base, IdMixin, TenantMixin, UpdatedTimestampsMixin):
    __tablename__ = "keyword_universe"
    __table_args__ = (
        UniqueConstraint("tenant_id", "keyword", name="uq_ku_tenant_keyword"),
        Index("ix_ku_tenant_priority", "tenant_id", "priority_score"),
    )

    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    # 1キーワードに最大3つのクラスタを割当てる(例: ["dx","local_osaka","vendor_search"])
    cluster_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    intent: Mapped[str | None] = mapped_column(Text)
    is_geographic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    gsc_imp_12m: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gsc_clicks_12m: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gsc_avg_position: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    suggest_derivative_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    competitor_coverage_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    llm_self_cite_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    llm_competitor_cite_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    priority_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="0"
    )
    # 'high_demand_no_coverage' | 'near_top_3' | 'low_demand' | None
    opportunity_flag: Mapped[str | None] = mapped_column(Text)

    source_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    last_aggregated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
