from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin


class KpiLog(Base, IdMixin, TenantMixin):
    __tablename__ = "kpi_logs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", name="uq_kpi_logs_tenant_date"),
        Index("ix_kpi_logs_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    sessions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    avg_position: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ai_citation_count: Mapped[int | None] = mapped_column(Integer)
    named_search_count: Mapped[int | None] = mapped_column(Integer)
    inquiries_count: Mapped[int | None] = mapped_column(Integer)
