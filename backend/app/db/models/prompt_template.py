from sqlalchemy import Boolean, Enum, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TimestampsMixin
from app.db.models.enums import AIUseCaseEnum


class PromptTemplate(Base, IdMixin, TimestampsMixin):
    """プロンプト本文は ai_engine/prompts/<file>.md がソース。

    本テーブルはファイルパスとバージョンのみ保持する。
    複数バージョンを保持して切替可能にする(古いバージョンを残す)。
    """

    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("use_case", "version", name="uq_prompt_templates_use_case_version"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    use_case: Mapped[AIUseCaseEnum] = mapped_column(
        Enum(AIUseCaseEnum, name="ai_use_case", native_enum=True, create_type=False),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
