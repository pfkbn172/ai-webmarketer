"""GA4 リファラ別日次セッション。

GA4 の sessionSource(参照元ホスト・キーワード)と sessionMedium
(referral / organic / cpc / (none)=Direct など)で分解した日次セッション。
全流入を保存する(AI 専用の ga4_ai_referral_daily と違い、ホワイトリスト無し)。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4ReferralDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_referral_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "source",
            "medium",
            name="uq_ga4_ref_d_tenant_date_src_med",
        ),
        Index("ix_ga4_ref_d_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    medium: Mapped[str] = mapped_column(String(64), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
