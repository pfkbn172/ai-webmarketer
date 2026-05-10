"""GA4 llms_txt_fetch イベントの日次集計(クローラー名別)。"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4LlmsTxtFetchDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_llms_txt_fetch_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "crawler_name", name="uq_ga4_llms_tenant_date_name"
        ),
        Index("ix_ga4_llms_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    crawler_name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
