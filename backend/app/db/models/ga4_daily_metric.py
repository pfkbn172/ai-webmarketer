"""GA4 の日次メトリクス。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4DailyMetric(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_daily_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", name="uq_ga4_daily_tenant_date"),
        Index("ix_ga4_daily_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    users: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    bounce_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    organic_sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
