from datetime import datetime

from sqlalchemy import CHAR, DateTime, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin


class Report(Base, IdMixin, TenantMixin):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", "report_type", name="uq_reports_tenant_period_type"),
    )

    period: Mapped[str] = mapped_column(CHAR(7), nullable=False)  # 'YYYY-MM'
    report_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'monthly' | 'weekly'
    summary_html: Mapped[str | None] = mapped_column(Text)
    action_plan: Mapped[dict | None] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
