"""異常検知: 順位急落・引用率急減・到達不能等を閾値比較で検知する。

仕様書 4.4.3 / 8.4。AI には任せず純コード判定。
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.citation_log import CitationLog
from app.db.models.gsc_query_metric import GscQueryMetric


@dataclass(frozen=True, slots=True)
class Anomaly:
    kind: str  # 'rank_drop' | 'citation_drop' | ...
    detail: str
    severity: str  # 'low' | 'medium' | 'high'


async def detect(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    rank_drop_threshold: int = 10,
    citation_drop_ratio: float = 0.5,
) -> list[Anomaly]:
    today = date.today()
    last_week = today - timedelta(days=7)
    prev_week = today - timedelta(days=14)
    out: list[Anomaly] = []

    # 順位急落: 同一クエリで前週と今週の position 平均比較
    stmt = (
        select(
            GscQueryMetric.query_text,
            GscQueryMetric.date,
            GscQueryMetric.position,
        )
        .where(
            GscQueryMetric.tenant_id == tenant_id,
            GscQueryMetric.date >= prev_week,
        )
    )
    rows = list((await session.execute(stmt)).all())
    by_query: dict[str, list[tuple[date, float]]] = {}
    for r in rows:
        if r.position is None:
            continue
        by_query.setdefault(r.query_text, []).append((r.date, float(r.position)))
    for q, points in by_query.items():
        recent = [p for d, p in points if d >= last_week]
        prior = [p for d, p in points if prev_week <= d < last_week]
        if not recent or not prior:
            continue
        avg_recent = sum(recent) / len(recent)
        avg_prior = sum(prior) / len(prior)
        delta = avg_recent - avg_prior  # positive = ランク悪化(数値が大きいほど低順位)
        if delta >= rank_drop_threshold:
            out.append(
                Anomaly(
                    kind="rank_drop",
                    detail=f"クエリ '{q}' 平均順位 {avg_prior:.1f} → {avg_recent:.1f}(+{delta:.1f})",
                    severity="high" if delta >= 20 else "medium",
                )
            )

    # 引用率急減: 直近 7 日 vs 前週の self_cited 率
    citation_stmt = (
        select(CitationLog.query_date, CitationLog.self_cited)
        .where(
            CitationLog.tenant_id == tenant_id,
            CitationLog.query_date >= prev_week,
        )
    )
    cites = list((await session.execute(citation_stmt)).all())
    if cites:
        recent = [c.self_cited for c in cites if c.query_date >= last_week]
        prior = [c.self_cited for c in cites if prev_week <= c.query_date < last_week]
        if recent and prior:
            r_rate = sum(1 for x in recent if x) / len(recent)
            p_rate = sum(1 for x in prior if x) / len(prior)
            if p_rate > 0 and r_rate < p_rate * citation_drop_ratio:
                out.append(
                    Anomaly(
                        kind="citation_drop",
                        detail=f"引用率 {p_rate:.1%} → {r_rate:.1%}",
                        severity="high",
                    )
                )

    return out
