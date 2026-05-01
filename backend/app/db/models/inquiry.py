from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin
from app.db.models.enums import AiOriginEnum, InquirySourceEnum, InquiryStatusEnum


class Inquiry(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "inquiries"
    __table_args__ = (
        Index("ix_inquiries_tenant_received", "tenant_id", "received_at"),
    )

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    company_size: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    source_channel: Mapped[InquirySourceEnum] = mapped_column(
        Enum(InquirySourceEnum, name="inquiry_source", native_enum=True, create_type=False),
        nullable=False,
    )
    ai_origin: Mapped[AiOriginEnum | None] = mapped_column(
        Enum(AiOriginEnum, name="ai_origin", native_enum=True, create_type=False),
    )
    status: Mapped[InquiryStatusEnum] = mapped_column(
        Enum(InquiryStatusEnum, name="inquiry_status", native_enum=True, create_type=False),
        nullable=False,
        server_default=InquiryStatusEnum.new.value,
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
