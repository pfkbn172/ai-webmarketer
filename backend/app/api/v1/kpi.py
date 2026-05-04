"""ダッシュボード用 KPI API。"""

import statistics
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
    # 7 日移動平均(セッション基準)とその外れ値判定。
    sessions_ma7: float | None = None
    is_anomaly: bool = False


class KpiMetric(BaseModel):
    """ある期間の KPI 値 + 比較期間との変化率(%)+ 比較期間の値 + 前年同期比。"""

    value: int
    prev_period_value: int
    delta_pct: float | None  # null = 比較不能(前期間が 0 等)
    prev_year_value: int | None = None
    yoy_pct: float | None = None


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


def _build_series_with_ma_and_anomaly(rows: list) -> list[KpiPoint]:
    """各 KpiLog 行に 7 日移動平均と異常値フラグを付与した KpiPoint リストを返す。

    異常値判定: 7 日移動平均 ± 2σ を外れたら anomaly = True(z-score > 2)。
    最低 7 行ない場合は計算しない(False / None のまま)。
    """
    sessions_arr: list[float] = [(r.sessions or 0) for r in rows]
    out: list[KpiPoint] = []
    for i, r in enumerate(rows):
        ma: float | None = None
        anomaly = False
        if i >= 6:
            window = sessions_arr[i - 6 : i + 1]
            ma = round(sum(window) / 7, 1)
            if len(window) >= 7:
                try:
                    sd = statistics.stdev(window)
                    if sd > 0:
                        z = abs((sessions_arr[i] - ma) / sd)
                        anomaly = z > 2.0
                except statistics.StatisticsError:
                    pass
        out.append(
            KpiPoint(
                date=r.date,
                sessions=r.sessions,
                ai_citation_count=r.ai_citation_count,
                inquiries_count=r.inquiries_count,
                sessions_ma7=ma,
                is_anomaly=anomaly,
            )
        )
    return out


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
    # 前年同期(うるう年は単純に 365 日引きで近似)
    yoy_end = end - timedelta(days=365)
    yoy_start = start - timedelta(days=365)

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
    series = _build_series_with_ma_and_anomaly(rows)
    sessions_total = sum((r.sessions or 0) for r in rows)
    citation_total = await _count_citations(session, tenant_id, start, end)
    inq_total = await _count_inquiries(session, tenant_id, start, end)
    contents_published = await _count_contents(session, tenant_id, start, end)

    # 前期間集計
    prev_sessions = await _sum_sessions(session, tenant_id, prev_start, prev_end)
    prev_citations = await _count_citations(session, tenant_id, prev_start, prev_end)
    prev_inquiries = await _count_inquiries(session, tenant_id, prev_start, prev_end)
    prev_contents = await _count_contents(session, tenant_id, prev_start, prev_end)

    # 前年同期集計
    yoy_sessions = await _sum_sessions(session, tenant_id, yoy_start, yoy_end)
    yoy_citations = await _count_citations(session, tenant_id, yoy_start, yoy_end)
    yoy_inquiries = await _count_inquiries(session, tenant_id, yoy_start, yoy_end)
    yoy_contents = await _count_contents(session, tenant_id, yoy_start, yoy_end)

    metrics = {
        "ai_citation_count": KpiMetric(
            value=int(citation_total),
            prev_period_value=int(prev_citations),
            delta_pct=_delta_pct(citation_total, prev_citations),
            prev_year_value=int(yoy_citations),
            yoy_pct=_delta_pct(citation_total, yoy_citations),
        ),
        "sessions": KpiMetric(
            value=int(sessions_total),
            prev_period_value=int(prev_sessions),
            delta_pct=_delta_pct(sessions_total, prev_sessions),
            prev_year_value=int(yoy_sessions),
            yoy_pct=_delta_pct(sessions_total, yoy_sessions),
        ),
        "inquiries_count": KpiMetric(
            value=int(inq_total),
            prev_period_value=int(prev_inquiries),
            delta_pct=_delta_pct(inq_total, prev_inquiries),
            prev_year_value=int(yoy_inquiries),
            yoy_pct=_delta_pct(inq_total, yoy_inquiries),
        ),
        "contents_published": KpiMetric(
            value=int(contents_published),
            prev_period_value=int(prev_contents),
            delta_pct=_delta_pct(contents_published, prev_contents),
            prev_year_value=int(yoy_contents),
            yoy_pct=_delta_pct(contents_published, yoy_contents),
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
