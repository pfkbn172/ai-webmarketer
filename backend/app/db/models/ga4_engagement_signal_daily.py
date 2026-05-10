"""GA4 エンゲージメント系イベントの統合日次集計。

低カーディナリティ・低重要度の以下イベント群をまとめる:
- returning_visitor_engaged
- content_share / url_copy
- internal_link_click
- contact_confirm_view

`sub_key` は二次ディメンション(share_method 等)。値が無い時は `'-'`。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4EngagementSignalDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_engagement_signal_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "event_name",
            "sub_key",
            name="uq_ga4_engsig_tenant_date_evt_sub",
        ),
        Index("ix_ga4_engsig_tenant_date", "tenant_id", "date"),
        Index("ix_ga4_engsig_tenant_date_evt", "tenant_id", "date", "event_name"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    sub_key: Mapped[str] = mapped_column(String(255), nullable=False, server_default="-")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
