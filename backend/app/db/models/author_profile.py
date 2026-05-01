from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class AuthorProfile(Base, IdMixin, TenantMixin, TimestampsMixin):
    """E-E-A-T シグナル。テナントあたり 1:N(複数著者対応、Q9 確定)。"""

    __tablename__ = "author_profiles"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str | None] = mapped_column(Text)
    works_for: Mapped[str | None] = mapped_column(Text)
    alumni_of: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    credentials: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    expertise: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    publications: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    speaking_engagements: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    awards: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    bio_short: Mapped[str | None] = mapped_column(Text)
    bio_long: Mapped[str | None] = mapped_column(Text)
    social_profiles: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
