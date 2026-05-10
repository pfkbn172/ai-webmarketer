"""GA4 outbound_click イベントの日次集計(カテゴリ × ドメイン別)。

outbound_category は `ai` / `social` / `booking` / `other` のいずれか。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4OutboundClickDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_outbound_click_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "outbound_category",
            "link_domain",
            name="uq_ga4_outb_tenant_date_cat_dom",
        ),
        Index("ix_ga4_outb_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    outbound_category: Mapped[str] = mapped_column(String(32), nullable=False)
    link_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
