from sqlalchemy import Boolean, Index, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class TargetQuery(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "target_queries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "query_text", name="uq_target_queries_tenant_text"),
        Index("ix_target_queries_tenant_active", "tenant_id", "is_active"),
    )

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_id: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    expected_conversion: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    search_intent: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
