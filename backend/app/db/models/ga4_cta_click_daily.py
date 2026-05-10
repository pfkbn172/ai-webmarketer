"""GA4 cta_click イベントの日次集計(LP × CTA 位置別)。

LP セッション数(`lp_sessions`)は同 lp_id の CTR 計算用に二次クエリで埋める。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4CtaClickDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_cta_click_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "lp_id",
            "cta_id",
            name="uq_ga4_cta_tenant_date_lp_cta",
        ),
        Index("ix_ga4_cta_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    lp_id: Mapped[str] = mapped_column(String(128), nullable=False)
    cta_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lp_sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
