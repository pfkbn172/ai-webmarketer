"""今日の3アクション(daily_action_recommender が毎朝生成)。

ホーム画面の主役データ。
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class DailyAction(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "daily_actions"
    __table_args__ = (
        Index("ix_da_tenant_generated", "tenant_id", "generated_at"),
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    action_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1〜3
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # 'red' | 'yellow' | 'green'
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    target_url: Mapped[str | None] = mapped_column(Text)
    related_keyword: Mapped[str | None] = mapped_column(Text)
