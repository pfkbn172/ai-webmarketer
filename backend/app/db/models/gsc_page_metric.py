"""GSC のページ(URL)別日次メトリクス。

クエリ単位の集計とは別に、URL × 日次で clicks / impressions / position / ctr を保存する。
記事単位の伸び・順位推移を分析するために必要。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class GscPageMetric(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "gsc_page_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", "page", name="uq_gsc_pm_tenant_date_page"),
        Index("ix_gsc_pm_tenant_date", "tenant_id", "date"),
        Index("ix_gsc_pm_tenant_page", "tenant_id", "page"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    page: Mapped[str] = mapped_column(Text, nullable=False)  # 完全 URL
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    position: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
