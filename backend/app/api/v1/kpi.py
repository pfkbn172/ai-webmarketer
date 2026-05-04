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
from app.db.models.ga4_daily_metric import Ga4DailyMetric
from app.db.models.inquiry import Inquiry

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


class DataCoverage(BaseModel):
    """各データソースの DB 蓄積開始日。YoY が出せるかをフロントで判定するのに使う。"""

    sessions_since: date | None = None
    citations_since: date | None = None
    inquiries_since: date | None = None
    contents_since: date | None = None


class KpiSummaryOut(BaseModel):
    period_days: int
    ai_citation_count: int
    sessions: int
    inquiries_count: int
    contents_published: int
    series: list[KpiPoint]
    # Phase 2 拡張: 各 KPI に前期間比較を付ける
    metrics: dict[str, KpiMetric]
    coverage: DataCoverage


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


def _build_series_with_ma_and_anomaly(
    *,
    start: date,
    end: date,
    sessions_by_date: dict[date, int],
    citations_by_date: dict[date, int],
    inquiries_by_date: dict[date, int],
) -> list[KpiPoint]:
    """期間内の各日について sessions / citations / inquiries を結合し、
    7 日移動平均と異常値フラグを付与した KpiPoint リストを返す。

    異常値判定: 7 日移動平均 ± 2σ を外れたら anomaly = True(z-score > 2)。
    """
    days_count = (end - start).days + 1
    dates = [start + timedelta(days=i) for i in range(days_count)]
    sessions_arr: list[float] = [sessions_by_date.get(d, 0) for d in dates]

    out: list[KpiPoint] = []
    for i, d in enumerate(dates):
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
                date=d,
                sessions=int(sessions_arr[i]),
                ai_citation_count=citations_by_date.get(d, 0),
                inquiries_count=inquiries_by_date.get(d, 0),
                sessions_ma7=ma,
                is_anomaly=anomaly,
            )
        )
    return out


async def _sum_sessions(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> int:
    """ga4_daily_metrics から期間合計セッションを返す。"""
    return int(
        (
            await session.scalar(
                select(func.coalesce(func.sum(Ga4DailyMetric.sessions), 0)).where(
                    Ga4DailyMetric.tenant_id == tenant_id,
                    Ga4DailyMetric.date.between(start, end),
                )
            )
        )
        or 0
    )


async def _sessions_by_date(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> dict[date, int]:
    rows = (
        await session.execute(
            select(Ga4DailyMetric.date, Ga4DailyMetric.sessions).where(
                Ga4DailyMetric.tenant_id == tenant_id,
                Ga4DailyMetric.date.between(start, end),
            )
        )
    ).all()
    return {r.date: int(r.sessions or 0) for r in rows}


async def _citations_by_date(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> dict[date, int]:
    rows = (
        await session.execute(
            select(
                CitationLog.query_date, func.count(CitationLog.id).label("c")
            )
            .where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date.between(start, end),
                CitationLog.self_cited.is_(True),
            )
            .group_by(CitationLog.query_date)
        )
    ).all()
    return {r.query_date: int(r.c or 0) for r in rows}


async def _inquiries_by_date(
    session: AsyncSession, tenant_id: uuid.UUID, start: date, end: date
) -> dict[date, int]:
    rows = (
        await session.execute(
            select(
                func.date(Inquiry.received_at).label("d"),
                func.count(Inquiry.id).label("c"),
            )
            .where(
                Inquiry.tenant_id == tenant_id,
                func.date(Inquiry.received_at).between(start, end),
            )
            .group_by(func.date(Inquiry.received_at))
        )
    ).all()
    return {r.d: int(r.c or 0) for r in rows}


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

    sessions_map = await _sessions_by_date(session, tenant_id, start, end)
    citations_map = await _citations_by_date(session, tenant_id, start, end)
    inquiries_map = await _inquiries_by_date(session, tenant_id, start, end)
    series = _build_series_with_ma_and_anomaly(
        start=start,
        end=end,
        sessions_by_date=sessions_map,
        citations_by_date=citations_map,
        inquiries_by_date=inquiries_map,
    )
    sessions_total = sum(sessions_map.values())
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

    coverage = DataCoverage(
        sessions_since=await session.scalar(
            select(func.min(Ga4DailyMetric.date)).where(
                Ga4DailyMetric.tenant_id == tenant_id
            )
        ),
        citations_since=await session.scalar(
            select(func.min(CitationLog.query_date)).where(
                CitationLog.tenant_id == tenant_id
            )
        ),
        inquiries_since=await session.scalar(
            select(func.min(func.date(Inquiry.received_at))).where(
                Inquiry.tenant_id == tenant_id
            )
        ),
        contents_since=await session.scalar(
            select(func.min(func.date(Content.published_at))).where(
                Content.tenant_id == tenant_id,
                Content.status == ContentStatusEnum.published,
            )
        ),
    )

    return KpiSummaryOut(
        period_days=days,
        ai_citation_count=int(citation_total),
        sessions=int(sessions_total),
        inquiries_count=int(inq_total),
        contents_published=int(contents_published),
        series=series,
        metrics=metrics,
        coverage=coverage,
    )
