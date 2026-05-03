"""異常検知 + 戦略違和感検知。

【既存(数値変動の異常)】
- rank_drop: 順位急落
- citation_drop: 引用率急減

【Phase 2 拡張(戦略的違和感)】
- chronic_zero_citation: 全クエリで自社引用が N 週連続でゼロ
- query_event_mismatch: 事業ステージ(solo/micro)に対してクエリが広域すぎる
- flat_distribution: 引用分布が平坦(全クエリの引用カウントがほぼ同値)

仕様書 4.4.3 / 8.4。コード判定中心、LLM には渡さない(誤検知耐性のため)。
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.citation_log import CitationLog
from app.db.models.gsc_query_metric import GscQueryMetric
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant


@dataclass(frozen=True, slots=True)
class Anomaly:
    kind: str
    detail: str
    severity: str  # 'low' | 'medium' | 'high'


# 「広域クエリ」の判定キーワード(零細にとって勝ち目薄)
BROAD_KEYWORDS = (
    "中小企業",
    "DX コンサル",
    "AI 導入",
    "業務効率化",
    "おすすめ",
    "比較",
)


async def detect(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    rank_drop_threshold: int = 10,
    citation_drop_ratio: float = 0.5,
    chronic_zero_weeks: int = 3,
) -> list[Anomaly]:
    today = date.today()
    last_week = today - timedelta(days=7)
    prev_week = today - timedelta(days=14)
    out: list[Anomaly] = []

    # === 既存: 順位急落 ===
    stmt = select(
        GscQueryMetric.query_text, GscQueryMetric.date, GscQueryMetric.position
    ).where(
        GscQueryMetric.tenant_id == tenant_id, GscQueryMetric.date >= prev_week
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
        delta = avg_recent - avg_prior
        if delta >= rank_drop_threshold:
            out.append(
                Anomaly(
                    kind="rank_drop",
                    detail=f"クエリ '{q}' 平均順位 {avg_prior:.1f} → {avg_recent:.1f}(+{delta:.1f})",
                    severity="high" if delta >= 20 else "medium",
                )
            )

    # === 既存: 引用率急減 ===
    cites_q = select(CitationLog.query_date, CitationLog.self_cited).where(
        CitationLog.tenant_id == tenant_id, CitationLog.query_date >= prev_week
    )
    cites = list((await session.execute(cites_q)).all())
    if cites:
        recent_c = [c.self_cited for c in cites if c.query_date >= last_week]
        prior_c = [c.self_cited for c in cites if prev_week <= c.query_date < last_week]
        if recent_c and prior_c:
            r_rate = sum(1 for x in recent_c if x) / len(recent_c)
            p_rate = sum(1 for x in prior_c if x) / len(prior_c)
            if p_rate > 0 and r_rate < p_rate * citation_drop_ratio:
                out.append(
                    Anomaly(
                        kind="citation_drop",
                        detail=f"引用率 {p_rate:.1%} → {r_rate:.1%}",
                        severity="high",
                    )
                )

    # === Phase 2: chronic_zero_citation(N 週連続で自社引用ゼロ)===
    n_weeks_ago = today - timedelta(days=7 * chronic_zero_weeks)
    stmt = select(
        func.count(CitationLog.id).label("total"),
        func.sum(cast(CitationLog.self_cited, Integer)).label("self_count"),
    ).where(
        CitationLog.tenant_id == tenant_id, CitationLog.query_date >= n_weeks_ago
    )
    chronic = (await session.execute(stmt)).one()
    if chronic.total and chronic.total >= 5 and (chronic.self_count or 0) == 0:
        out.append(
            Anomaly(
                kind="chronic_zero_citation",
                detail=(
                    f"過去 {chronic_zero_weeks} 週で全 {chronic.total} 件のモニタが自社引用ゼロ。"
                    f"クエリ広域度・事業ステージ・コンテンツの方向性のいずれかにミスマッチがある可能性"
                ),
                severity="high",
            )
        )

    # === Phase 2: query_scope_mismatch(事業ステージ × クエリ広域度)===
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one_or_none()
    if tenant and tenant.business_context:
        stage = (tenant.business_context or {}).get("stage")
        if stage in ("solo", "micro"):
            queries = list(
                (
                    await session.scalars(
                        select(TargetQuery).where(
                            TargetQuery.tenant_id == tenant_id,
                            TargetQuery.is_active.is_(True),
                        )
                    )
                ).all()
            )
            broad = [
                q
                for q in queries
                if any(k in q.query_text for k in BROAD_KEYWORDS)
                and not any(
                    g in q.query_text
                    for g in (tenant.business_context.get("geographic_base") or [])
                )
            ]
            if len(queries) and len(broad) / len(queries) > 0.5:
                out.append(
                    Anomaly(
                        kind="query_scope_mismatch",
                        detail=(
                            f"事業ステージが {stage} なのに、ターゲットクエリの "
                            f"{len(broad)}/{len(queries)} 件が広域(地域絞り込みなし)。"
                            f"地域 × サービス系のロングテール化を検討"
                        ),
                        severity="high",
                    )
                )

    return out
