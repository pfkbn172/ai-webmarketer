"""GA4 tool_use_complete イベントの日次集計(ツール名別)。

WP 側で `data-tool-complete="<name>"` 属性が未設定の場合、当面は 0 行のまま。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4ToolUseDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_tool_use_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "tool_name", name="uq_ga4_tool_tenant_date_name"
        ),
        Index("ix_ga4_tool_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
