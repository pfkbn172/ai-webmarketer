"""GA4 から取得した AI チャット経由の日次セッション。

ChatGPT / Claude / Perplexity / Gemini / Copilot などの参照ホストごとに
日次のセッション数を保持し、ダッシュボードで「AI 経由の流入」を可視化する。
"""

from datetime import date

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class Ga4AiReferralDaily(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ga4_ai_referral_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "source_host", name="uq_ga4_ai_ref_tenant_date_host"
        ),
        Index("ix_ga4_ai_ref_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    source_host: Mapped[str] = mapped_column(String(255), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
