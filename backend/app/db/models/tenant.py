from sqlalchemy import Boolean, Enum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, UpdatedTimestampsMixin
from app.db.models.enums import ComplianceTypeEnum


class Tenant(Base, IdMixin, UpdatedTimestampsMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    compliance_type: Mapped[ComplianceTypeEnum] = mapped_column(
        Enum(ComplianceTypeEnum, name="compliance_type", native_enum=True, create_type=False),
        nullable=False,
        server_default=ComplianceTypeEnum.general.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Phase 2: 戦略思考 LLM プロンプトに渡す事業文脈。
    # 構造はゆるく、UI で自由編集可能。主要キー:
    #   stage / geographic_base / geographic_expansion / unique_value /
    #   primary_offerings / target_customer / weak_segments / strong_segments /
    #   compliance_constraints
    business_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
