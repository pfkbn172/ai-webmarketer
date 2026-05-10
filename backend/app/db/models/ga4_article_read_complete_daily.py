"""GA4 article_read_complete イベントの日次集計(ページ別 + 完読率算出用 PV)。

`page_views` は完読率分母として同一ページ・同一日の page_view eventCount を保持する。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4ArticleReadCompleteDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_article_read_complete_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "page_path", name="uq_ga4_arc_tenant_date_path"
        ),
        Index("ix_ga4_arc_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    page_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    page_views: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
