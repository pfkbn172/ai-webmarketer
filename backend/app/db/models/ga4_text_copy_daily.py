"""GA4 text_copy イベントの日次集計(ページ × content_type 別)。

content_type は `code` / `table` / `text` のいずれか(本体 analytics.js 仕様)。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4TextCopyDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_text_copy_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "page_path",
            "content_type",
            name="uq_ga4_txc_tenant_date_path_type",
        ),
        Index("ix_ga4_txc_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    page_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
