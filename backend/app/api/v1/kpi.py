"""ダッシュボード用 KPI API。"""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.citation_log import CitationLog
from app.db.models.content import Content
from app.db.models.enums import ContentStatusEnum
from app.db.models.inquiry import Inquiry
from app.db.models.kpi_log import KpiLog

router = APIRouter(prefix="/kpi", tags=["kpi"])


class KpiPoint(BaseModel):
    date: date
    sessions: int | None
    ai_citation_count: int | None
    inquiries_count: int | None


class KpiSummaryOut(BaseModel):
    period_days: int
    ai_citation_count: int
    sessions: int
    inquiries_count: int
    contents_published: int
    series: list[KpiPoint]


@router.get("/summary", response_model=KpiSummaryOut)
async def kpi_summary(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> KpiSummaryOut:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    end = date.today()
    start = end - timedelta(days=days)

    rows = list(
        (
            await session.scalars(
                select(KpiLog)
                .where(
                    KpiLog.tenant_id == tenant_id,
                    KpiLog.date.between(start, end),
                )
                .order_by(KpiLog.date)
            )
        ).all()
    )
    series = [
        KpiPoint(
            date=r.date,
            sessions=r.sessions,
            ai_citation_count=r.ai_citation_count,
            inquiries_count=r.inquiries_count,
        )
        for r in rows
    ]
    sessions_total = sum((r.sessions or 0) for r in rows)
    citation_total = (
        await session.scalar(
            select(func.count(CitationLog.id)).where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date.between(start, end),
                CitationLog.self_cited.is_(True),
            )
        )
        or 0
    )
    inq_total = (
        await session.scalar(
            select(func.count(Inquiry.id)).where(
                Inquiry.tenant_id == tenant_id,
                func.date(Inquiry.received_at).between(start, end),
            )
        )
        or 0
    )
    contents_published = (
        await session.scalar(
            select(func.count(Content.id)).where(
                Content.tenant_id == tenant_id,
                Content.status == ContentStatusEnum.published,
                func.date(Content.published_at).between(start, end),
            )
        )
        or 0
    )

    return KpiSummaryOut(
        period_days=days,
        ai_citation_count=int(citation_total),
        sessions=int(sessions_total),
        inquiries_count=int(inq_total),
        contents_published=int(contents_published),
        series=series,
    )
