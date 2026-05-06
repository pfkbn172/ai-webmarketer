"""keyword_universe を集計するメインロジック。

入力ソース:
  - gsc_query_metrics: 直近12ヶ月の query_text 別 imp / clicks / avg_position
  - keyword_suggestions: source 別の derived_keyword 出現回数
  - competitor_posts: 各 keyword が title に何社で含まれるか(unique competitor 数)
  - citation_logs × target_queries: query_text 別 self_cite_rate / competitor_cite_rate

出力:
  keyword_universe (tenant_id, keyword) の upsert + opportunity_flag/priority_score 付与。
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.keyword_universe import KeywordUniverse
from app.keyword_engine.cluster_matcher import classify_all
from app.keyword_engine.normalizer import normalize
from app.keyword_engine.priority_calculator import (
    PriorityInputs,
    calculate_score,
    determine_opportunity_flag,
)
from app.utils.logger import get_logger

log = get_logger(__name__)


GSC_LOOKBACK_DAYS = 365  # 「過去12ヶ月」


@dataclass(slots=True)
class _Row:
    keyword: str
    gsc_imp_12m: int = 0
    gsc_clicks_12m: int = 0
    gsc_avg_position: float | None = None
    suggest_derivative_count: int = 0
    competitor_coverage_count: int = 0
    llm_self_cite_rate: float | None = None
    llm_competitor_cite_rate: float | None = None
    source_breakdown: dict = None  # type: ignore[assignment]


async def aggregate_universe(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """tenant_id 単位で集計→upsert。upsert件数を返す。"""
    started = datetime.now(UTC)
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

    # 1) 各ソースから keyword 単位のメトリクスを集計
    rows: dict[str, _Row] = {}

    await _merge_from_gsc(session, tenant_id, rows)
    await _merge_from_suggestions(session, tenant_id, rows)
    await _merge_from_competitor_posts(session, tenant_id, rows)
    await _merge_from_citations(session, tenant_id, rows)

    if not rows:
        log.info("aggregator_no_data", tenant_id=str(tenant_id))
        return 0

    # 2) クラスタ分類 + priority_score / opportunity_flag を計算
    upsert_payload = []
    now = datetime.now(UTC)
    for keyword, r in rows.items():
        clusters = classify_all(keyword)
        # is_geographic と intent は割当てクラスタの中で「最も具体的な1個」を採用。
        # 具体的=clusters.yaml 上位(local_hiranoku > local_osaka > vendor_search > dx ...)
        is_geographic = any(c.is_geographic for c in clusters)
        intent = next((c.intent for c in clusters if c.intent), None)

        inputs = PriorityInputs(
            gsc_imp_12m=r.gsc_imp_12m,
            gsc_avg_position=r.gsc_avg_position,
            suggest_derivative_count=r.suggest_derivative_count,
            competitor_coverage_count=r.competitor_coverage_count,
            llm_self_cite_rate=r.llm_self_cite_rate,
            is_geographic=is_geographic,
        )
        score = calculate_score(inputs)
        flag = determine_opportunity_flag(inputs)

        upsert_payload.append(
            {
                "tenant_id": tenant_id,
                "keyword": keyword,
                "cluster_ids": [c.cluster_id for c in clusters],
                "intent": intent,
                "is_geographic": is_geographic,
                "gsc_imp_12m": r.gsc_imp_12m,
                "gsc_clicks_12m": r.gsc_clicks_12m,
                "gsc_avg_position": r.gsc_avg_position,
                "suggest_derivative_count": r.suggest_derivative_count,
                "competitor_coverage_count": r.competitor_coverage_count,
                "llm_self_cite_rate": r.llm_self_cite_rate,
                "llm_competitor_cite_rate": r.llm_competitor_cite_rate,
                "priority_score": score,
                "opportunity_flag": flag,
                "source_breakdown": r.source_breakdown or {},
                "last_aggregated_at": now,
                "updated_at": now,
            }
        )

    # 3) upsert(unique key: tenant_id+keyword)
    #    Postgres プロトコルは1ステートメント 32767 パラメータが上限。
    #    1行=17列なのでバッチ 1500 行(=25500 パラメータ)で安全に分割する。
    update_column_names = (
        "cluster_ids",
        "intent",
        "is_geographic",
        "gsc_imp_12m",
        "gsc_clicks_12m",
        "gsc_avg_position",
        "suggest_derivative_count",
        "competitor_coverage_count",
        "llm_self_cite_rate",
        "llm_competitor_cite_rate",
        "priority_score",
        "opportunity_flag",
        "source_breakdown",
        "last_aggregated_at",
        "updated_at",
    )
    BATCH_SIZE = 1500
    for i in range(0, len(upsert_payload), BATCH_SIZE):
        chunk = upsert_payload[i : i + BATCH_SIZE]
        stmt = pg_insert(KeywordUniverse).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ku_tenant_keyword",
            set_={c: stmt.excluded[c] for c in update_column_names},
        )
        await session.execute(stmt)
    await session.commit()

    elapsed = (datetime.now(UTC) - started).total_seconds()
    log.info(
        "aggregator_done",
        tenant_id=str(tenant_id),
        upserted=len(upsert_payload),
        elapsed_s=round(elapsed, 1),
    )
    return len(upsert_payload)


# ---------------------------------------------------------------------------
# ソース別マージ
# ---------------------------------------------------------------------------

async def _merge_from_gsc(
    session: AsyncSession, tenant_id: uuid.UUID, rows: dict[str, _Row]
) -> None:
    cutoff = datetime.now(UTC).date() - timedelta(days=GSC_LOOKBACK_DAYS)
    sql = text(
        """
        SELECT query_text,
               SUM(impressions)::int AS imp,
               SUM(clicks)::int      AS clk,
               AVG(position)::float  AS pos
        FROM gsc_query_metrics
        WHERE tenant_id = :tid AND date >= :cutoff
        GROUP BY query_text
        """
    )
    res = await session.execute(sql, {"tid": tenant_id, "cutoff": cutoff})
    for q, imp, clk, pos in res:
        kw = normalize(q)
        if not kw:
            continue
        r = rows.setdefault(kw, _Row(keyword=kw))
        r.gsc_imp_12m += int(imp or 0)
        r.gsc_clicks_12m += int(clk or 0)
        # 同じ keyword に複数の正規化前バリエーションが集約されることもあるため、
        # 最後の pos で上書きではなく imp 加重平均にしたいが、Phase 2 では
        # 単純に imp が最大の元レコードの pos を採用する近似で十分。
        r.gsc_avg_position = float(pos) if pos is not None else r.gsc_avg_position
        bd = r.source_breakdown or {}
        bd["gsc"] = True
        r.source_breakdown = bd


async def _merge_from_suggestions(
    session: AsyncSession, tenant_id: uuid.UUID, rows: dict[str, _Row]
) -> None:
    """derivative_count は「**derived_keyword が何種類の異なる seed から派生したか**」。

    背景: Google + Bing × 1seed では最大 2 にしかならず、「広く認識されている語ほど高くなる」
    という意図(計画書 §3.4)を反映できない。
    そこで「ユニーク seed 数」を採用し、複数シードから現れる横断ワードを高評価する。

    source_breakdown には観測の内訳(google/bing/competitor 件数)も併記。
    """
    sql = text(
        """
        SELECT derived_keyword,
               COUNT(DISTINCT seed_keyword) FILTER (WHERE seed_keyword IS NOT NULL) AS uniq_seeds,
               SUM(CASE WHEN source='google_suggest' THEN 1 ELSE 0 END) AS g_cnt,
               SUM(CASE WHEN source='bing_suggest'   THEN 1 ELSE 0 END) AS b_cnt,
               SUM(CASE WHEN source LIKE 'competitor_%' THEN 1 ELSE 0 END) AS c_cnt
        FROM keyword_suggestions
        WHERE tenant_id = :tid
        GROUP BY derived_keyword
        """
    )
    res = await session.execute(sql, {"tid": tenant_id})
    for derived, uniq_seeds, g_cnt, b_cnt, c_cnt in res:
        kw = normalize(derived)
        if not kw:
            continue
        r = rows.setdefault(kw, _Row(keyword=kw))
        # ユニーク seed 数(seed が NULL の競合見出し由来は 0 換算)
        r.suggest_derivative_count = max(
            r.suggest_derivative_count, int(uniq_seeds or 0)
        )
        bd = r.source_breakdown or {}
        bd["uniq_seeds"] = int(uniq_seeds or 0)
        if g_cnt:
            bd["google"] = bd.get("google", 0) + int(g_cnt)
        if b_cnt:
            bd["bing"] = bd.get("bing", 0) + int(b_cnt)
        if c_cnt:
            bd["competitor_headings"] = bd.get("competitor_headings", 0) + int(c_cnt)
        r.source_breakdown = bd


async def _merge_from_competitor_posts(
    session: AsyncSession, tenant_id: uuid.UUID, rows: dict[str, _Row]
) -> None:
    """既存の rows[keyword] に対して、competitor_posts.title への含有数を計上する。
    Phase 2 では「rows に既に存在する keyword」だけを対象にスキャンする(N×M を避ける)。
    """
    if not rows:
        return

    # 競合タイトルを全部取って、Python 側で keyword 含有判定
    sql = text(
        """
        SELECT competitor_id, title
        FROM competitor_posts
        WHERE tenant_id = :tid AND title IS NOT NULL
        """
    )
    res = await session.execute(sql, {"tid": tenant_id})
    titles = [(comp_id, normalize(title or "")) for comp_id, title in res]
    if not titles:
        return

    for kw, r in rows.items():
        if len(kw) < 2:
            continue
        seen_competitors: set = set()
        for comp_id, ntitle in titles:
            if not ntitle:
                continue
            if kw in ntitle:
                seen_competitors.add(comp_id)
        if seen_competitors:
            r.competitor_coverage_count = max(
                r.competitor_coverage_count, len(seen_competitors)
            )
            bd = r.source_breakdown or {}
            bd["competitors"] = len(seen_competitors)
            r.source_breakdown = bd


async def _merge_from_citations(
    session: AsyncSession, tenant_id: uuid.UUID, rows: dict[str, _Row]
) -> None:
    sql = text(
        """
        SELECT tq.query_text,
               COUNT(cl.id)::int AS total,
               SUM(CASE WHEN cl.self_cited THEN 1 ELSE 0 END)::int AS self_cited
        FROM citation_logs cl
        JOIN target_queries tq ON tq.id = cl.query_id
        WHERE cl.tenant_id = :tid
        GROUP BY tq.query_text
        """
    )
    res = await session.execute(sql, {"tid": tenant_id})
    for q, total, self_cited in res:
        kw = normalize(q)
        if not kw:
            continue
        r = rows.setdefault(kw, _Row(keyword=kw))
        if total and total > 0:
            r.llm_self_cite_rate = round(float(self_cited or 0) / float(total), 4)
            bd = r.source_breakdown or {}
            bd["llm_observations"] = int(total)
            r.source_breakdown = bd
