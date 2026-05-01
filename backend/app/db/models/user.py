from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TimestampsMixin
from app.db.models.enums import UserRoleEnum


class User(Base, IdMixin, TimestampsMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(
        Enum(UserRoleEnum, name="user_role", native_enum=True, create_type=False),
        nullable=False,
        server_default=UserRoleEnum.client.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
