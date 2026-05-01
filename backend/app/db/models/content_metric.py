import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin


class ContentMetric(Base, IdMixin, TenantMixin):
    """日次のコンテンツメトリクス。tenant_id を非正規化して RLS を効かせる。"""

    __tablename__ = "content_metrics"
    __table_args__ = (
        UniqueConstraint("content_id", "date", name="uq_content_metrics_content_date"),
        Index("ix_content_metrics_tenant_date", "tenant_id", "date"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    citations: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
