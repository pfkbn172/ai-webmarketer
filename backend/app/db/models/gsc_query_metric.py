"""GSC のクエリ別日次メトリクス。

implementation_plan 5 章の概念モデルには明記されていなかったが、
仕様書 4.1.1 の「クエリ別クリック・表示回数・CTR・平均掲載順位」を保存するため、
W1-10 で追加した補助テーブル。RLS 対象。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._mixins import IdMixin, TenantMixin, TimestampsMixin


class GscQueryMetric(Base, IdMixin, TenantMixin, TimestampsMixin):
    __tablename__ = "gsc_query_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", "query_text", name="uq_gsc_qm_tenant_date_query"),
        Index("ix_gsc_qm_tenant_date", "tenant_id", "date"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    position: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
