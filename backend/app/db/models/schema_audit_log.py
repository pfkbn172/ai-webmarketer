import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class SchemaAuditLog(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "schema_audit_logs"
    __table_args__ = (
        Index("ix_schema_audit_tenant_date", "tenant_id", "audit_date"),
    )

    content_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    audit_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    missing_fields: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    raw_jsonld: Mapped[dict | None] = mapped_column(JSONB)
