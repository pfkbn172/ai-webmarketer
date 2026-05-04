"""マーケティング施策タイムライン。

ダッシュボードのグラフ上に「いつ何をしたか」をマーカーで重ねるためのテーブル。
日付 × カテゴリ × タイトル + 任意の説明文を保持する。
"""

from datetime import date

from sqlalchemy import Date, Enum, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin
from app.db.models.enums import MarketingActionCategoryEnum


class MarketingAction(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "marketing_actions"
    __table_args__ = (
        Index("ix_marketing_actions_tenant_date", "tenant_id", "action_date"),
    )

    action_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[MarketingActionCategoryEnum] = mapped_column(
        Enum(
            MarketingActionCategoryEnum,
            name="marketing_action_category",
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        server_default=MarketingActionCategoryEnum.other.value,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
