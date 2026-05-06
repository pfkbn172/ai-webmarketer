"""GA4 の (日付 × 時間帯) 別セッション。

曜日 × 時間帯ヒートマップで「よく見られている時間帯」を可視化するために使う。
GA4 の `dateHour` ディメンション(YYYYMMDDHH 文字列)を date と hour(0〜23)に
分解して保存する。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4HourlyMetric(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_hourly_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", "hour", name="uq_ga4_hourly_tenant_date_hour"),
        Index("ix_ga4_hourly_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    hour: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0〜23
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
