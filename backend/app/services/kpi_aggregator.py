"""日次 KPI 集計サービス。GSC / GA4 / citation_logs / inquiries から
kpi_logs に 1 行を upsert する。

named_search_count(指名検索):
    GSC のクエリテキストに自社のブランド名 / ドメイン由来語(ILIKE 部分一致)を
    含むクエリの clicks 合計。テナントの name と domain の主要語(. 区切り先頭)を
    マッチ語として使う。例: tenant.name='kiseeeen', domain='kiseeeen.co.jp' なら
    "kiseeeen" を含むクエリすべての clicks を合算。
"""

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.citation_log import CitationLog
from app.db.models.ga4_daily_metric import Ga4DailyMetric
from app.db.models.gsc_query_metric import GscQueryMetric
from app.db.models.inquiry import Inquiry
from app.db.models.kpi_log import KpiLog
from app.db.models.tenant import Tenant


def _branded_terms(name: str, domain: str) -> list[str]:
    """指名検索の判定語を抽出する。

    - tenant.name(空白で分割した各トークン、2 文字以上)
    - domain の TLD より前のラベル(例: kiseeeen.co.jp → 'kiseeeen')
    重複除去・小文字化済みで返す。
    """
    out: set[str] = set()
    for token in (name or "").split():
        t = token.strip().lower()
        if len(t) >= 2:
            out.add(t)
    if domain:
        first_label = domain.split(".")[0].lower()
        if len(first_label) >= 2:
            out.add(first_label)
    return sorted(out)


async def aggregate_for_date(
    session: AsyncSession, tenant_id: uuid.UUID, target_date: date
) -> KpiLog:
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one_or_none()

    # GSC 集計
    gsc = (
        await session.execute(
            select(
                func.coalesce(func.sum(GscQueryMetric.clicks), 0),
                func.coalesce(func.sum(GscQueryMetric.impressions), 0),
                func.avg(GscQueryMetric.position),
            ).where(
                GscQueryMetric.tenant_id == tenant_id,
                GscQueryMetric.date == target_date,
            )
        )
    ).one()
    clicks, impressions, avg_position = gsc

    # 指名検索 clicks 合計
    named_count: int | None = None
    if tenant is not None:
        terms = _branded_terms(tenant.name, tenant.domain)
        if terms:
            patterns = [GscQueryMetric.query_text.ilike(f"%{t}%") for t in terms]
            named_count = (
                await session.scalar(
                    select(func.coalesce(func.sum(GscQueryMetric.clicks), 0)).where(
                        GscQueryMetric.tenant_id == tenant_id,
                        GscQueryMetric.date == target_date,
                        or_(*patterns),
                    )
                )
                or 0
            )

    # GA4 集計
    ga4 = (
        await session.scalars(
            select(Ga4DailyMetric).where(
                Ga4DailyMetric.tenant_id == tenant_id,
                Ga4DailyMetric.date == target_date,
            )
        )
    ).one_or_none()
    sessions = ga4.sessions if ga4 else None

    # 引用集計
    cite_count = (
        await session.scalar(
            select(func.count(CitationLog.id)).where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date == target_date,
                CitationLog.self_cited.is_(True),
            )
        )
        or 0
    )

    # 問い合わせ件数
    inq_count = (
        await session.scalar(
            select(func.count(Inquiry.id)).where(
                Inquiry.tenant_id == tenant_id,
                func.date(Inquiry.received_at) == target_date,
            )
        )
        or 0
    )

    stmt = pg_insert(KpiLog).values(
        tenant_id=tenant_id,
        date=target_date,
        sessions=sessions,
        clicks=clicks,
        impressions=impressions,
        avg_position=avg_position,
        ai_citation_count=cite_count,
        named_search_count=named_count,
        inquiries_count=inq_count,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_kpi_logs_tenant_date",
        set_={
            "sessions": stmt.excluded.sessions,
            "clicks": stmt.excluded.clicks,
            "impressions": stmt.excluded.impressions,
            "avg_position": stmt.excluded.avg_position,
            "ai_citation_count": stmt.excluded.ai_citation_count,
            "named_search_count": stmt.excluded.named_search_count,
            "inquiries_count": stmt.excluded.inquiries_count,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return KpiLog()  # placeholder
