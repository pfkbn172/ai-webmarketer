"""競合サイトの最新記事(RSS 経由で収集)。"""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class CompetitorPost(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "competitor_posts"
    __table_args__ = (
        UniqueConstraint("competitor_id", "url", name="uq_competitor_posts_url"),
        Index("ix_competitor_posts_tenant_published", "tenant_id", "published_at"),
    )

    competitor_id: Mapped[_uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("competitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text)
