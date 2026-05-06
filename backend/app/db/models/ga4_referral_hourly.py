"""GA4 リファラ × 時間帯セッション。

スパイク日に「13 時台に X.com から大量流入」のような時間軸での原因特定に使う。
cardinality を抑えるため、サイズが膨らんだら「日次の Top N に絞ってから時間別取得」の
分割が必要(現状 Phase 1 は 1 サイトなので無問題)。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4ReferralHourly(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_referral_hourly"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "hour",
            "source",
            "medium",
            name="uq_ga4_ref_h_tenant_date_hour_src_med",
        ),
        Index("ix_ga4_ref_h_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    hour: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0..23
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    medium: Mapped[str] = mapped_column(String(64), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
