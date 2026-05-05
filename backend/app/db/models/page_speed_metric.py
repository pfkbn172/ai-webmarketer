"""PageSpeed Insights のスコアと Core Web Vitals を保存。

mobile/desktop の各ストラテジで、URL × 取得日に LCP / CLS / INP / 性能スコアを格納。
SEO 順位の足を引っ張る速度劣化を可視化する。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class PageSpeedMetric(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "page_speed_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "page_url", "strategy",
            name="uq_psm_tenant_date_url_strategy",
        ),
        Index("ix_psm_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)  # 'mobile' | 'desktop'
    performance_score: Mapped[int | None] = mapped_column(Integer)  # 0〜100
    lcp_ms: Mapped[int | None] = mapped_column(Integer)
    cls: Mapped[float | None] = mapped_column(Numeric(6, 3))
    inp_ms: Mapped[int | None] = mapped_column(Integer)
    fcp_ms: Mapped[int | None] = mapped_column(Integer)
    ttfb_ms: Mapped[int | None] = mapped_column(Integer)
