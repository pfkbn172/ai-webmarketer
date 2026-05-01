import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin
from app.db.models.enums import AIProviderEnum, AIUseCaseEnum


class AIProviderConfig(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "use_case", name="uq_ai_provider_configs_tenant_use_case"),
    )

    use_case: Mapped[AIUseCaseEnum] = mapped_column(
        Enum(AIUseCaseEnum, name="ai_use_case", native_enum=True, create_type=False),
        nullable=False,
    )
    provider: Mapped[AIProviderEnum] = mapped_column(
        Enum(AIProviderEnum, name="ai_provider", native_enum=True, create_type=False),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="SET NULL"),
    )
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default="0.70")
    max_tokens: Mapped[int] = mapped_column(Integer, server_default="2000")
    fallback_provider: Mapped[AIProviderEnum | None] = mapped_column(
        Enum(AIProviderEnum, name="ai_provider", native_enum=True, create_type=False),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
