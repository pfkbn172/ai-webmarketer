import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin
from app.db.models.enums import JobStatusEnum


class JobExecutionLog(Base, IdMixin):
    """ジョブ実行履歴。tenant_id は nullable(システムジョブ用)。

    RLS は適用しない(管理者がすべてのジョブ履歴を見られるべきため、
    tenant フィルタはアプリ層で必要に応じて行う)。
    """

    __tablename__ = "job_execution_logs"
    __table_args__ = (
        Index("ix_job_logs_name_started", "job_name", "started_at"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        index=True,
    )
    job_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatusEnum] = mapped_column(
        Enum(JobStatusEnum, name="job_status", native_enum=True, create_type=False),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(Text)
    job_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
