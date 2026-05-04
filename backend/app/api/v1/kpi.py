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


class KpiMetric(BaseModel):
    """ある期間の KPI 値 + 比較期間との変化率(%)+ 比較期間の値。"""

    value: int
    prev_period_value: int
    delta_pct: float | None  # null = 比較不能(前期間が 0 等)


class KpiSummaryOut(BaseModel):
    period_days: int
    ai_citation_count: int
    sessions: int
    inquiries_count: int
    contents_published: int
    series: list[KpiPoint]
    # Phase 2 拡張: 各 KPI に前期間比較を付ける
    metrics: dict[str, KpiMetric]


def _delta_pct(curr: int, prev: int) -> float | None:
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 1)


async def _count_citations(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> int:
    return (
        await session.scalar(
            select(func.count(CitationLog.id)).where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date.between(start, end),
                CitationLog.self_cited.is_(True),
            )
        )
    ) or 0


async def _count_inquiries(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> int:
    return (
        await session.scalar(
            select(func.count(Inquiry.id)).where(
                Inquiry.tenant_id == tenant_id,
                func.date(Inquiry.received_at).between(start, end),
            )
        )
    ) or 0


async def _count_contents(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> int:
    return (
        await session.scalar(
            select(func.count(Content.id)).where(
                Content.tenant_id == tenant_id,
                Content.status == ContentStatusEnum.published,
                func.date(Content.published_at).between(start, end),
            )
        )
    ) or 0


async def _sum_sessions(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> int:
    rows = list(
        (
            await session.scalars(
                select(KpiLog).where(
                    KpiLog.tenant_id == tenant_id,
                    KpiLog.date.between(start, end),
                )
            )
        ).all()
    )
    return sum((r.sessions or 0) for r in rows)


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
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

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
    citation_total = await _count_citations(session, tenant_id, start, end)
    inq_total = await _count_inquiries(session, tenant_id, start, end)
    contents_published = await _count_contents(session, tenant_id, start, end)

    # 前期間集計
    prev_sessions = await _sum_sessions(session, tenant_id, prev_start, prev_end)
    prev_citations = await _count_citations(session, tenant_id, prev_start, prev_end)
    prev_inquiries = await _count_inquiries(session, tenant_id, prev_start, prev_end)
    prev_contents = await _count_contents(session, tenant_id, prev_start, prev_end)

    metrics = {
        "ai_citation_count": KpiMetric(
            value=int(citation_total),
            prev_period_value=int(prev_citations),
            delta_pct=_delta_pct(citation_total, prev_citations),
        ),
        "sessions": KpiMetric(
            value=int(sessions_total),
            prev_period_value=int(prev_sessions),
            delta_pct=_delta_pct(sessions_total, prev_sessions),
        ),
        "inquiries_count": KpiMetric(
            value=int(inq_total),
            prev_period_value=int(prev_inquiries),
            delta_pct=_delta_pct(inq_total, prev_inquiries),
        ),
        "contents_published": KpiMetric(
            value=int(contents_published),
            prev_period_value=int(prev_contents),
            delta_pct=_delta_pct(contents_published, prev_contents),
        ),
    }

    return KpiSummaryOut(
        period_days=days,
        ai_citation_count=int(citation_total),
        sessions=int(sessions_total),
        inquiries_count=int(inq_total),
        contents_published=int(contents_published),
        series=series,
        metrics=metrics,
    )
