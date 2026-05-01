import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, UpdatedTimestampsMixin
from app.db.models.enums import ContentStatusEnum


class Content(Base, IdMixin, TenantMixin, UpdatedTimestampsMixin):
    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "url", name="uq_contents_tenant_url"),
        Index("ix_contents_tenant_status", "tenant_id", "status", "published_at"),
    )

    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ContentStatusEnum] = mapped_column(
        Enum(ContentStatusEnum, name="content_status", native_enum=True, create_type=False),
        nullable=False,
        server_default=ContentStatusEnum.draft.value,
    )
    pillar_id: Mapped[str | None] = mapped_column(Text)
    cluster_id: Mapped[str | None] = mapped_column(Text)
    schema_score: Mapped[int | None] = mapped_column(SmallInteger)
    draft_md: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wp_post_id: Mapped[int | None] = mapped_column(BigInteger)
    primary_author_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("author_profiles.id", ondelete="SET NULL"),
    )
