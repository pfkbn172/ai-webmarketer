from sqlalchemy import Boolean, Enum, Text
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
