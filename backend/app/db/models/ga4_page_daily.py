"""GA4 の pagePath 別日次セッション。

サイト全体のセッションだけでなく、URL ごとの流入を保存して
「どの記事が伸びている / 落ちている」を判断できるようにする。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4PageDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_page_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "page_path", name="uq_ga4_pd_tenant_date_path"
        ),
        Index("ix_ga4_pd_tenant_date", "tenant_id", "date"),
        Index("ix_ga4_pd_tenant_path", "tenant_id", "page_path"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    page_path: Mapped[str] = mapped_column(Text, nullable=False)  # /blog/foo の形
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    users: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
