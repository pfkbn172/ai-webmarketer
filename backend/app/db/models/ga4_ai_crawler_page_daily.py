"""GA4 ai_crawler_visit イベントの日次集計(ページ × クローラー名別)。

カーディナリティが高くなるため、収集側で `limit=1000`/日 で抑える。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4AiCrawlerPageDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_ai_crawler_page_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "crawler_name",
            "page_path",
            name="uq_ga4_ai_crawl_pg_tenant_date_name_path",
        ),
        Index("ix_ga4_ai_crawl_pg_tenant_date", "tenant_id", "date"),
        Index(
            "ix_ga4_ai_crawl_pg_tenant_date_name",
            "tenant_id",
            "date",
            "crawler_name",
        ),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    crawler_name: Mapped[str] = mapped_column(String(128), nullable=False)
    page_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
