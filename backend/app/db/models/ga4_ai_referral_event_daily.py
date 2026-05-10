"""GA4 ai_referral イベントの日次集計(イベントベース)。

既存 `ga4_ai_referral_daily` は sessionSource ベースの session 集計だが、
こちらは本体の analytics.js から送信される `ai_referral` イベントを
`customEvent:ai_referrer_domain` 別に集計したもの。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4AiReferralEventDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_ai_referral_event_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "ai_referrer_domain",
            name="uq_ga4_ai_ref_evt_tenant_date_dom",
        ),
        Index("ix_ga4_ai_ref_evt_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    ai_referrer_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
