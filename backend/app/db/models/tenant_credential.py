from sqlalchemy import Enum, LargeBinary, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, UpdatedTimestampsMixin
from app.db.models.enums import CredentialProviderEnum


class TenantCredential(Base, IdMixin, TenantMixin, UpdatedTimestampsMixin):
    __tablename__ = "tenant_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_credentials_tenant_provider"),
    )

    provider: Mapped[CredentialProviderEnum] = mapped_column(
        Enum(CredentialProviderEnum, name="credential_provider", native_enum=True, create_type=False),
        nullable=False,
    )
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
