"""ダッシュボード専用の集約 API。

複数のテーブルから「マーケター視点で 1 画面に出すべき」データを集めて返す。
KPI summary は kpi.py に分離、本ファイルはそれ以外のブロックを担当。

提供するエンドポイント:
- /dashboard/cluster-citation : クラスタ別引用率
- /dashboard/top-queries      : GSC 主要クエリ TOP 10
- /dashboard/citation-heatmap : クエリ × LLM のミニヒートマップ(TOP 5 クエリ)
- /dashboard/next-actions     : Next Actions チェックリスト(永続化付き)
- /dashboard/objectives       : 月次目標と進捗
- /dashboard/channel-breakdown: 流入経路の内訳(GA4 channel)
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.citation_log import CitationLog
from app.db.models.gsc_query_metric import GscQueryMetric
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


# === C. クラスタ別引用率 ===


class ClusterCitation(BaseModel):
    cluster_id: str
    total: int
    self_cited: int
    rate: float  # 0.0〜1.0


@router.get("/cluster-citation", response_model=list[ClusterCitation])
async def cluster_citation(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ClusterCitation]:
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    queries = list(
        (
            await session.scalars(
                select(TargetQuery).where(TargetQuery.tenant_id == tenant_id)
            )
        ).all()
    )
    qmap = {q.id: q.cluster_id or "unknown" for q in queries}
    logs = list(
        (
            await session.scalars(
                select(CitationLog).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_date.between(start, end),
                )
            )
        ).all()
    )
    by_cluster: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "self_cited": 0}
    )
    for log_ in logs:
        c = qmap.get(log_.query_id, "unknown")
        by_cluster[c]["total"] += 1
        if log_.self_cited:
            by_cluster[c]["self_cited"] += 1
    out: list[ClusterCitation] = []
    for c, v in sorted(by_cluster.items()):
        rate = v["self_cited"] / v["total"] if v["total"] else 0
        out.append(
            ClusterCitation(
                cluster_id=c, total=v["total"], self_cited=v["self_cited"], rate=rate
            )
        )
    return out


# === E. 主要クエリ TOP 10(GSC) ===


class TopQueryRow(BaseModel):
    query_text: str
    clicks: int
    impressions: int
    ctr: float | None
    avg_position: float | None


@router.get("/top-queries", response_model=list[TopQueryRow])
async def top_queries(
    days: int = 30,
    limit: int = 10,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[TopQueryRow]:
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(
            GscQueryMetric.query_text,
            func.sum(GscQueryMetric.clicks).label("clicks"),
            func.sum(GscQueryMetric.impressions).label("impressions"),
            func.avg(GscQueryMetric.ctr).label("ctr"),
            func.avg(GscQueryMetric.position).label("position"),
        )
        .where(
            GscQueryMetric.tenant_id == tenant_id,
            GscQueryMetric.date.between(start, end),
        )
        .group_by(GscQueryMetric.query_text)
        .order_by(func.sum(GscQueryMetric.impressions).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        TopQueryRow(
            query_text=r.query_text,
            clicks=int(r.clicks or 0),
            impressions=int(r.impressions or 0),
            ctr=float(r.ctr) if r.ctr is not None else None,
            avg_position=float(r.position) if r.position is not None else None,
        )
        for r in rows
    ]


# === B. 引用ヒートマップ(TOP 5 クエリ × LLM)===


class HeatmapCell(BaseModel):
    llm_provider: str
    self_cited: int
    total: int


class HeatmapRow(BaseModel):
    query_text: str
    cluster_id: str | None
    cells: list[HeatmapCell]


@router.get("/citation-heatmap", response_model=list[HeatmapRow])
async def citation_heatmap(
    days: int = 28,
    limit: int = 5,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[HeatmapRow]:
    """priority 高い順にクエリを TOP N、LLM ごとの自社引用 / 全モニタ数。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    queries = list(
        (
            await session.scalars(
                select(TargetQuery)
                .where(
                    TargetQuery.tenant_id == tenant_id,
                    TargetQuery.is_active.is_(True),
                )
                .order_by(TargetQuery.priority.desc(), TargetQuery.query_text)
                .limit(limit)
            )
        ).all()
    )
    qmap = {q.id: (q.query_text, q.cluster_id) for q in queries}
    if not queries:
        return []

    logs = list(
        (
            await session.scalars(
                select(CitationLog).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_id.in_([q.id for q in queries]),
                    CitationLog.query_date.between(start, end),
                )
            )
        ).all()
    )
    # query_id -> llm -> [self, total]
    by_q: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for log_ in logs:
        cell = by_q[log_.query_id][log_.llm_provider.value]
        cell[1] += 1
        if log_.self_cited:
            cell[0] += 1
    out: list[HeatmapRow] = []
    for q in queries:
        text_q, cluster = qmap[q.id]
        cells = [
            HeatmapCell(llm_provider=llm, self_cited=v[0], total=v[1])
            for llm, v in by_q.get(q.id, {}).items()
        ]
        out.append(HeatmapRow(query_text=text_q, cluster_id=cluster, cells=cells))
    return out


# === D. 流入経路内訳(GA4 / Phase 1 では sessions 全体のみなので簡易実装)===


class ChannelBreakdown(BaseModel):
    channel: str
    sessions: int


@router.get("/channel-breakdown", response_model=list[ChannelBreakdown])
async def channel_breakdown(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChannelBreakdown]:
    """GA4 の Organic Search セッション(取得済)+ それ以外を Other として返す。

    Phase 1 では Organic Search 数のみ ga4_daily_metrics に保管されているので、
    全体セッション - Organic で Other を計算する暫定実装。Phase 2 でチャネル別
    集計を ga4 collector に追加予定。
    """
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    res = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(sessions), 0) AS total, "
                "COALESCE(SUM(organic_sessions), 0) AS organic "
                "FROM ga4_daily_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).one()
    total = int(res.total or 0)
    organic = int(res.organic or 0)
    other = max(0, total - organic)
    return [
        ChannelBreakdown(channel="Organic Search", sessions=organic),
        ChannelBreakdown(channel="Other", sessions=other),
    ]


# === H. Next Actions チェックリスト ===

# 簡易実装: tenants.business_context.next_actions[] に永続化する
# (将来的に専用テーブルへ昇格可能、現状はテナントあたり最大 5 件想定)


class NextAction(BaseModel):
    id: str  # ローカル一意 ID(テナント内で重複しなければ可)
    text: str
    rationale: str | None = None
    completed: bool = False


@router.get("/next-actions", response_model=list[NextAction])
async def get_next_actions(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[NextAction]:
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}
    items = bc.get("next_actions", []) or []
    out: list[NextAction] = []
    for item in items:
        if isinstance(item, dict):
            try:
                out.append(NextAction(**item))
            except Exception:
                continue
    return out


class NextActionsBulk(BaseModel):
    items: list[NextAction]


@router.put("/next-actions", response_model=list[NextAction])
async def replace_next_actions(
    body: NextActionsBulk,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[NextAction]:
    """完全置換。AI 提言の採用 / 完了状態の更新も同じ API で。"""
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = dict(tenant.business_context or {})
    bc["next_actions"] = [item.model_dump() for item in body.items]
    tenant.business_context = bc
    await session.commit()
    return body.items


@router.post("/next-actions/from-ai", response_model=list[NextAction])
async def generate_next_actions_with_ai(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[NextAction]:
    """戦略レビューを実行してその next_actions をそのまま採用する。"""
    from app.ai_engine.usecases.strategic_review import run_strategic_review

    await _set_ctx(session, tenant_id)
    review = await run_strategic_review(session, tenant_id)
    raw_actions = review.get("next_actions", []) or []
    items: list[NextAction] = []
    for i, a in enumerate(raw_actions):
        if not isinstance(a, dict):
            continue
        items.append(
            NextAction(
                id=f"ai-{i + 1}",
                text=a.get("action", ""),
                rationale=a.get("rationale"),
                completed=False,
            )
        )

    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = dict(tenant.business_context or {})
    bc["next_actions"] = [i.model_dump() for i in items]
    tenant.business_context = bc
    await session.commit()
    return items


# === I. 月次目標 KPI 設定 + 進捗 ===

# tenants.business_context.objectives.{key} = {target: int, period: 'YYYY-MM'} に保管
# キー名は "monthly_sessions" / "monthly_citations" / "monthly_inquiries" / "monthly_contents"


class Objective(BaseModel):
    key: str
    label: str
    target: int
    current: int
    progress_pct: float  # 0.0〜100.0+


@router.get("/objectives", response_model=list[Objective])
async def list_objectives(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[Objective]:
    """設定された月次目標と、当月の現在値・進捗率を返す。"""
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}
    objectives = bc.get("objectives", {}) or {}
    if not isinstance(objectives, dict):
        return []

    today = date.today()
    month_start = today.replace(day=1)

    # 当月の各値を集計
    sessions_q = await session.execute(
        text(
            "SELECT COALESCE(SUM(sessions), 0) FROM ga4_daily_metrics "
            "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
        ),
        {"tid": str(tenant_id), "s": month_start, "e": today},
    )
    sessions_curr = int(sessions_q.scalar() or 0)
    citations_curr = (
        await session.scalar(
            select(func.count(CitationLog.id)).where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date.between(month_start, today),
                CitationLog.self_cited.is_(True),
            )
        )
        or 0
    )
    from app.db.models.content import Content
    from app.db.models.enums import ContentStatusEnum
    from app.db.models.inquiry import Inquiry

    inq_curr = (
        await session.scalar(
            select(func.count(Inquiry.id)).where(
                Inquiry.tenant_id == tenant_id,
                func.date(Inquiry.received_at).between(month_start, today),
            )
        )
        or 0
    )
    contents_curr = (
        await session.scalar(
            select(func.count(Content.id)).where(
                Content.tenant_id == tenant_id,
                Content.status == ContentStatusEnum.published,
                func.date(Content.published_at).between(month_start, today),
            )
        )
        or 0
    )

    label_map = {
        "monthly_sessions": "今月のセッション数",
        "monthly_citations": "今月の AI 引用数",
        "monthly_inquiries": "今月の問い合わせ数",
        "monthly_contents": "今月の公開記事数",
    }
    current_map = {
        "monthly_sessions": sessions_curr,
        "monthly_citations": citations_curr,
        "monthly_inquiries": inq_curr,
        "monthly_contents": contents_curr,
    }

    out: list[Objective] = []
    for key, label in label_map.items():
        cfg = objectives.get(key)
        if not isinstance(cfg, dict):
            continue
        try:
            target = int(cfg.get("target", 0))
        except (TypeError, ValueError):
            continue
        if target <= 0:
            continue
        current = int(current_map.get(key, 0))
        out.append(
            Objective(
                key=key,
                label=label,
                target=target,
                current=current,
                progress_pct=round(current / target * 100, 1),
            )
        )
    return out


class ObjectivesUpsertIn(BaseModel):
    monthly_sessions: int | None = None
    monthly_citations: int | None = None
    monthly_inquiries: int | None = None
    monthly_contents: int | None = None


@router.put("/objectives", response_model=list[Objective])
async def upsert_objectives(
    body: ObjectivesUpsertIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[Objective]:
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = dict(tenant.business_context or {})
    objs = dict(bc.get("objectives", {}) or {})
    for key in (
        "monthly_sessions",
        "monthly_citations",
        "monthly_inquiries",
        "monthly_contents",
    ):
        v = getattr(body, key)
        if v is None:
            continue
        if v <= 0:
            objs.pop(key, None)
        else:
            objs[key] = {"target": int(v)}
    bc["objectives"] = objs
    tenant.business_context = bc
    await session.commit()
    # 集計を返却
    if objs:
        return await list_objectives(tenant_id=tenant_id, session=session)
    return []


# === 競合パターン Top 3(strategic.py の競合パターンを再利用)===


class CompetitorPatternMini(BaseModel):
    domain: str
    count: int
    label: str


@router.get("/competitor-patterns-top", response_model=list[CompetitorPatternMini])
async def competitor_patterns_top(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CompetitorPatternMini]:
    from app.services.competitor_analysis import analyze_competitor_patterns

    await _set_ctx(session, tenant_id)
    items = await analyze_competitor_patterns(session, tenant_id, lookback_days=days, top_n=5)
    # candidate ラベルだけに絞って TOP 3 を返す
    out = [i for i in items if i["label"] == "candidate"][:3]
    return [CompetitorPatternMini(**i) for i in out]


# === AI 経由の流入(GA4 sessionSource ベース)===

# GA4 が返すホスト名 → 表示用ラベルへのマッピング。
# Ga4Client.AI_REFERRAL_HOSTS と一致させること。
_AI_HOST_LABEL: dict[str, str] = {
    "chatgpt.com": "ChatGPT",
    "chat.openai.com": "ChatGPT",
    "claude.ai": "Claude",
    "perplexity.ai": "Perplexity",
    "www.perplexity.ai": "Perplexity",
    "gemini.google.com": "Gemini",
    "bard.google.com": "Gemini",
    "copilot.microsoft.com": "Copilot",
    "www.bing.com": "Bing/Copilot",
}


class AiReferralRow(BaseModel):
    label: str
    source_host: str
    sessions: int


@router.get("/ai-referrals", response_model=list[AiReferralRow])
async def ai_referrals(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AiReferralRow]:
    """AI チャット(ChatGPT/Claude/Perplexity/Gemini/Copilot)経由のセッション。

    ホスト名ごとに集計し、同じサービスに属するホスト(例: chatgpt.com と
    chat.openai.com)はラベルでまとめる。0 件は返さない。
    """
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    rows = (
        await session.execute(
            text(
                "SELECT source_host, COALESCE(SUM(sessions), 0) AS sessions "
                "FROM ga4_ai_referral_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY source_host "
                "ORDER BY sessions DESC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    # 同ラベル(例 ChatGPT)に複数ホスト(chatgpt.com / chat.openai.com)が
    # 紐づくのでセッションを加算集約。代表 host は最大セッションのものを採用。
    agg: dict[str, dict] = defaultdict(lambda: {"sessions": 0, "top_host": "", "top": 0})
    for r in rows:
        host = r.source_host
        sessions = int(r.sessions or 0)
        if sessions <= 0:
            continue
        label = _AI_HOST_LABEL.get(host, host)
        bucket = agg[label]
        bucket["sessions"] += sessions
        if sessions > bucket["top"]:
            bucket["top"] = sessions
            bucket["top_host"] = host
    out = [
        AiReferralRow(label=label, source_host=v["top_host"], sessions=v["sessions"])
        for label, v in agg.items()
    ]
    out.sort(key=lambda r: r.sessions, reverse=True)
    return out


# === AIO 効果(2026-05 追加カスタムイベント由来) ============================

# 本体側の analytics.js が送る `ai_referral` / `ai_crawler_visit` /
# `llms_txt_fetch` イベントを、customEvent: ディメンションでブレイクダウン
# して見せるためのエンドポイント群。GA4 ディメンション登録から 24〜48 時間
# 経過しないとデータが伝播しないため、空配列を返すケースが正常系。


class AiReferralEventRow(BaseModel):
    ai_referrer_domain: str
    event_count: int


@router.get("/ai-referral-events", response_model=list[AiReferralEventRow])
async def ai_referral_events(
    days: int = 30,
    limit: int = 20,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AiReferralEventRow]:
    """ai_referral イベント × ai_referrer_domain の集計(TOP N)。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    rows = (
        await session.execute(
            text(
                "SELECT ai_referrer_domain, COALESCE(SUM(event_count), 0) AS event_count "
                "FROM ga4_ai_referral_event_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY ai_referrer_domain "
                "ORDER BY event_count DESC "
                "LIMIT :limit"
            ),
            {"tid": str(tenant_id), "s": start, "e": end, "limit": limit},
        )
    ).all()
    return [
        AiReferralEventRow(
            ai_referrer_domain=r.ai_referrer_domain,
            event_count=int(r.event_count or 0),
        )
        for r in rows
        if int(r.event_count or 0) > 0
    ]


class AiCrawlerByName(BaseModel):
    crawler_name: str
    event_count: int


class AiCrawlerSeriesPoint(BaseModel):
    date: date
    crawler_name: str
    event_count: int


class AiCrawlerVisitsOut(BaseModel):
    total: int
    by_crawler: list[AiCrawlerByName]
    series: list[AiCrawlerSeriesPoint]


@router.get("/ai-crawler-visits", response_model=AiCrawlerVisitsOut)
async def ai_crawler_visits(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> AiCrawlerVisitsOut:
    """ai_crawler_visit イベントの集計 + 折れ線用日別データ。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    by_crawler_rows = (
        await session.execute(
            text(
                "SELECT crawler_name, COALESCE(SUM(event_count), 0) AS event_count "
                "FROM ga4_ai_crawler_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY crawler_name "
                "ORDER BY event_count DESC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    series_rows = (
        await session.execute(
            text(
                "SELECT date, crawler_name, COALESCE(SUM(event_count), 0) AS event_count "
                "FROM ga4_ai_crawler_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY date, crawler_name "
                "ORDER BY date ASC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    by_crawler = [
        AiCrawlerByName(
            crawler_name=r.crawler_name, event_count=int(r.event_count or 0)
        )
        for r in by_crawler_rows
        if int(r.event_count or 0) > 0
    ]
    return AiCrawlerVisitsOut(
        total=sum(b.event_count for b in by_crawler),
        by_crawler=by_crawler,
        series=[
            AiCrawlerSeriesPoint(
                date=r.date,
                crawler_name=r.crawler_name,
                event_count=int(r.event_count or 0),
            )
            for r in series_rows
            if int(r.event_count or 0) > 0
        ],
    )


class AiCrawlerPageRow(BaseModel):
    page_path: str
    event_count: int
    top_crawler: str


@router.get("/ai-crawler-pages", response_model=list[AiCrawlerPageRow])
async def ai_crawler_pages(
    days: int = 30,
    limit: int = 10,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AiCrawlerPageRow]:
    """AI クローラーがアクセスした人気ページ TOP N(主クローラーつき)。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    rows = (
        await session.execute(
            text(
                "WITH agg AS ( "
                "  SELECT page_path, crawler_name, "
                "         COALESCE(SUM(event_count), 0) AS cnt "
                "  FROM ga4_ai_crawler_page_daily "
                "  WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "  GROUP BY page_path, crawler_name "
                "), "
                "ranked AS ( "
                "  SELECT page_path, crawler_name, cnt, "
                "         ROW_NUMBER() OVER ( "
                "             PARTITION BY page_path ORDER BY cnt DESC "
                "         ) AS rn "
                "  FROM agg "
                ") "
                "SELECT page_path, "
                "       MAX(CASE WHEN rn = 1 THEN crawler_name END) AS top_crawler, "
                "       SUM(cnt) AS total "
                "FROM ranked "
                "GROUP BY page_path "
                "ORDER BY total DESC "
                "LIMIT :limit"
            ),
            {"tid": str(tenant_id), "s": start, "e": end, "limit": limit},
        )
    ).all()
    return [
        AiCrawlerPageRow(
            page_path=r.page_path,
            event_count=int(r.total or 0),
            top_crawler=r.top_crawler or "",
        )
        for r in rows
        if int(r.total or 0) > 0
    ]


class LlmsTxtFetchByCrawler(BaseModel):
    crawler_name: str
    event_count: int


class LlmsTxtFetchSeriesPoint(BaseModel):
    date: date
    total: int


class LlmsTxtFetchOut(BaseModel):
    total: int
    by_crawler: list[LlmsTxtFetchByCrawler]
    series: list[LlmsTxtFetchSeriesPoint]


@router.get("/llms-txt-fetches", response_model=LlmsTxtFetchOut)
async def llms_txt_fetches(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> LlmsTxtFetchOut:
    """llms.txt の取得回数(クローラー別 + 日次トレンド)。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    by_crawler_rows = (
        await session.execute(
            text(
                "SELECT crawler_name, COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_llms_txt_fetch_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY crawler_name "
                "ORDER BY cnt DESC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    series_rows = (
        await session.execute(
            text(
                "SELECT date, COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_llms_txt_fetch_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY date "
                "ORDER BY date ASC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    by_crawler = [
        LlmsTxtFetchByCrawler(crawler_name=r.crawler_name, event_count=int(r.cnt or 0))
        for r in by_crawler_rows
        if int(r.cnt or 0) > 0
    ]
    return LlmsTxtFetchOut(
        total=sum(b.event_count for b in by_crawler),
        by_crawler=by_crawler,
        series=[
            LlmsTxtFetchSeriesPoint(date=r.date, total=int(r.cnt or 0))
            for r in series_rows
            if int(r.cnt or 0) > 0
        ],
    )


# === コンタクトファネル(2026-05 追加: contact_complete をキーイベント想定) ===


class ContactFunnelStep(BaseModel):
    label: str
    key: str
    count: int
    drop_off_pct: float | None  # 前ステップからの離脱率(0〜1)。step1 は null。


class ContactFunnelOut(BaseModel):
    period_days: int
    steps: list[ContactFunnelStep]


@router.get("/contact-funnel", response_model=ContactFunnelOut)
async def contact_funnel(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ContactFunnelOut:
    """`/contact/` 訪問 → confirm_view → conversions(contact_complete)の 3 ステップファネル。

    本プロパティではキーイベント = `contact_complete` のため、
    GA4 builtin `conversions` メトリクスがそのまま contact_complete 件数となる。
    """
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    # Step 1: /contact/ ページ訪問(ga4_page_daily.sessions 集計)
    s1 = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(sessions), 0) AS cnt "
                "FROM ga4_page_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "AND page_path = '/contact/'"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).scalar_one()

    # Step 2: contact_confirm_view イベント
    s2 = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_engagement_signal_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "AND event_name = 'contact_confirm_view'"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).scalar_one()

    # Step 3: conversions(== contact_complete on this property)
    s3 = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(conversions), 0) AS cnt "
                "FROM ga4_daily_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).scalar_one()

    s1, s2, s3 = int(s1 or 0), int(s2 or 0), int(s3 or 0)

    def _drop(prev: int, cur: int) -> float | None:
        if prev <= 0:
            return None
        return max(0.0, min(1.0, (prev - cur) / prev))

    return ContactFunnelOut(
        period_days=days,
        steps=[
            ContactFunnelStep(
                label="お問い合わせページ訪問",
                key="contact_page_view",
                count=s1,
                drop_off_pct=None,
            ),
            ContactFunnelStep(
                label="確認画面到達",
                key="contact_confirm_view",
                count=s2,
                drop_off_pct=_drop(s1, s2),
            ),
            ContactFunnelStep(
                label="送信完了 (contact_complete)",
                key="contact_complete",
                count=s3,
                drop_off_pct=_drop(s2, s3),
            ),
        ],
    )


# === コンテンツ品質(2026-05 追加: 完読率 / コピー / 外部リンク) ============


class ArticleReadCompletionRow(BaseModel):
    page_path: str
    event_count: int
    page_views: int
    completion_rate: float | None  # event_count / page_views(分母 0 のとき null)


@router.get("/article-read-completion", response_model=list[ArticleReadCompletionRow])
async def article_read_completion(
    days: int = 30,
    limit: int = 20,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ArticleReadCompletionRow]:
    """ページ別 完読率(article_read_complete / page_view)。PV >= 10 で絞ってノイズ抑制。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    rows = (
        await session.execute(
            text(
                "SELECT page_path, "
                "       COALESCE(SUM(event_count), 0) AS reads, "
                "       COALESCE(SUM(page_views), 0) AS pvs "
                "FROM ga4_article_read_complete_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY page_path "
                "HAVING COALESCE(SUM(page_views), 0) >= 10 "
                "ORDER BY (CASE WHEN SUM(page_views) > 0 "
                "               THEN SUM(event_count)::float / SUM(page_views) "
                "               ELSE 0 END) DESC, reads DESC "
                "LIMIT :limit"
            ),
            {"tid": str(tenant_id), "s": start, "e": end, "limit": limit},
        )
    ).all()
    out: list[ArticleReadCompletionRow] = []
    for r in rows:
        reads = int(r.reads or 0)
        pvs = int(r.pvs or 0)
        out.append(
            ArticleReadCompletionRow(
                page_path=r.page_path,
                event_count=reads,
                page_views=pvs,
                completion_rate=(reads / pvs) if pvs > 0 else None,
            )
        )
    return out


class TextCopyPageRow(BaseModel):
    page_path: str
    content_type: str
    event_count: int


class TextCopyOut(BaseModel):
    by_content_type: dict[str, int]  # {"code": ..., "table": ..., "text": ...}
    top_pages: list[TextCopyPageRow]


@router.get("/text-copy", response_model=TextCopyOut)
async def text_copy(
    days: int = 30,
    limit: int = 10,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> TextCopyOut:
    """text_copy イベント: content_type 別合計 + ページ TOP N(content_type 別)。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    by_type_rows = (
        await session.execute(
            text(
                "SELECT content_type, COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_text_copy_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY content_type"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    pages = (
        await session.execute(
            text(
                "SELECT page_path, content_type, COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_text_copy_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY page_path, content_type "
                "ORDER BY cnt DESC "
                "LIMIT :limit"
            ),
            {"tid": str(tenant_id), "s": start, "e": end, "limit": limit},
        )
    ).all()
    return TextCopyOut(
        by_content_type={r.content_type: int(r.cnt or 0) for r in by_type_rows},
        top_pages=[
            TextCopyPageRow(
                page_path=r.page_path,
                content_type=r.content_type,
                event_count=int(r.cnt or 0),
            )
            for r in pages
        ],
    )


class OutboundCategoryRow(BaseModel):
    outbound_category: str
    event_count: int


class OutboundDomainRow(BaseModel):
    link_domain: str
    outbound_category: str
    event_count: int


class OutboundClicksOut(BaseModel):
    by_category: list[OutboundCategoryRow]
    top_domains: list[OutboundDomainRow]


@router.get("/outbound-clicks", response_model=OutboundClicksOut)
async def outbound_clicks(
    days: int = 30,
    limit: int = 20,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> OutboundClicksOut:
    """外部リンククリック: カテゴリ別合計 + 上位ドメイン。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    cat_rows = (
        await session.execute(
            text(
                "SELECT outbound_category, COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_outbound_click_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY outbound_category "
                "ORDER BY cnt DESC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    domain_rows = (
        await session.execute(
            text(
                "SELECT link_domain, outbound_category, "
                "       COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_outbound_click_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY link_domain, outbound_category "
                "ORDER BY cnt DESC "
                "LIMIT :limit"
            ),
            {"tid": str(tenant_id), "s": start, "e": end, "limit": limit},
        )
    ).all()
    return OutboundClicksOut(
        by_category=[
            OutboundCategoryRow(
                outbound_category=r.outbound_category,
                event_count=int(r.cnt or 0),
            )
            for r in cat_rows
            if int(r.cnt or 0) > 0
        ],
        top_domains=[
            OutboundDomainRow(
                link_domain=r.link_domain,
                outbound_category=r.outbound_category,
                event_count=int(r.cnt or 0),
            )
            for r in domain_rows
            if int(r.cnt or 0) > 0
        ],
    )


# === LP 別パフォーマンス(2026-05 追加: cta_click) ==========================


class LpCtaByLpRow(BaseModel):
    lp_id: str
    event_count: int
    lp_sessions: int
    cvr: float | None  # event_count / lp_sessions


class LpCtaByPositionRow(BaseModel):
    cta_id: str
    event_count: int


class LpCtaClicksOut(BaseModel):
    by_lp: list[LpCtaByLpRow]
    by_position: list[LpCtaByPositionRow]


@router.get("/lp-cta-clicks", response_model=LpCtaClicksOut)
async def lp_cta_clicks(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> LpCtaClicksOut:
    """LP 別 CTA クリック数 + LP セッションからの CVR + ポジション(header/body)別。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    # LP 別: lp_sessions は同じ (date, lp_id) で重複するので MAX を取る(全 cta_id 行で同値)
    by_lp = (
        await session.execute(
            text(
                "WITH per_day AS ( "
                "  SELECT date, lp_id, "
                "         SUM(event_count) AS clicks, "
                "         MAX(lp_sessions) AS lp_sessions "
                "  FROM ga4_cta_click_daily "
                "  WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "  GROUP BY date, lp_id "
                ") "
                "SELECT lp_id, "
                "       COALESCE(SUM(clicks), 0) AS clicks, "
                "       COALESCE(SUM(lp_sessions), 0) AS lp_sessions "
                "FROM per_day "
                "GROUP BY lp_id "
                "ORDER BY clicks DESC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    by_position = (
        await session.execute(
            text(
                "SELECT cta_id, COALESCE(SUM(event_count), 0) AS cnt "
                "FROM ga4_cta_click_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY cta_id "
                "ORDER BY cnt DESC"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    return LpCtaClicksOut(
        by_lp=[
            LpCtaByLpRow(
                lp_id=r.lp_id,
                event_count=int(r.clicks or 0),
                lp_sessions=int(r.lp_sessions or 0),
                cvr=(int(r.clicks or 0) / int(r.lp_sessions))
                if int(r.lp_sessions or 0) > 0
                else None,
            )
            for r in by_lp
            if int(r.clicks or 0) > 0
        ],
        by_position=[
            LpCtaByPositionRow(
                cta_id=r.cta_id, event_count=int(r.cnt or 0)
            )
            for r in by_position
            if int(r.cnt or 0) > 0
        ],
    )


# === 記事/ページ単位のパフォーマンス ===

# GA4 の pagePath(/blog/foo) と GSC の page(完全 URL)を URL の path 部分でつなぐ。
# 完全一致しない場合は path で結合する。


class PagePerformanceRow(BaseModel):
    page_path: str
    title: str | None
    sessions: int
    clicks: int
    impressions: int
    ctr: float | None  # クリック率 0〜1。clicks / impressions(impressions=0 のとき null)
    avg_position: float | None
    citation_count: int  # 自社が引用された AI モニタログのうち、このページが含まれた回数


@router.get("/page-performance", response_model=list[PagePerformanceRow])
async def page_performance(
    days: int = 30,
    limit: int = 20,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[PagePerformanceRow]:
    """記事 × 流入数 × クリック × 順位 × 引用回数の TOP N。"""
    from app.db.models.content import Content as _Content

    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    # GA4 page_path 集計
    ga4_rows = (
        await session.execute(
            text(
                "SELECT page_path, COALESCE(SUM(sessions),0) AS sessions "
                "FROM ga4_page_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY page_path"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    ga4_map = {r.page_path: int(r.sessions or 0) for r in ga4_rows}

    # GSC page 集計
    gsc_rows = (
        await session.execute(
            text(
                "SELECT page, COALESCE(SUM(clicks),0) AS clicks, "
                "COALESCE(SUM(impressions),0) AS impressions, "
                "AVG(position) AS pos "
                "FROM gsc_page_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY page"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    # GSC の page は完全 URL のため、path 部分を抽出して GA4 と結合する
    import urllib.parse as _u

    gsc_by_path: dict[str, dict] = {}
    gsc_by_full: dict[str, dict] = {}
    for r in gsc_rows:
        full = r.page or ""
        try:
            path = _u.urlparse(full).path or full
        except ValueError:
            path = full
        v = {
            "clicks": int(r.clicks or 0),
            "impressions": int(r.impressions or 0),
            "position": float(r.pos) if r.pos is not None else None,
            "full_url": full,
        }
        gsc_by_full[full] = v
        gsc_by_path[path] = v

    # Content 一覧(URL → title)
    contents = list(
        (
            await session.scalars(
                select(_Content).where(_Content.tenant_id == tenant_id)
            )
        ).all()
    )
    title_by_url: dict[str, str] = {}
    title_by_path: dict[str, str] = {}
    for c in contents:
        if c.url:
            title_by_url[c.url] = c.title or ""
            try:
                p = _u.urlparse(c.url).path
                if p:
                    title_by_path[p] = c.title or ""
            except ValueError:
                pass

    # citation_log.cited_urls は JSONB array、self_cited=True 行のみ対象
    citation_rows = (
        await session.execute(
            text(
                "SELECT cited_urls FROM citation_logs "
                "WHERE tenant_id = :tid AND query_date BETWEEN :s AND :e "
                "AND self_cited = TRUE"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    citation_count_by_path: dict[str, int] = defaultdict(int)
    for row in citation_rows:
        urls = row.cited_urls or []
        if not isinstance(urls, list):
            continue
        for u in urls:
            if not isinstance(u, str):
                continue
            try:
                p = _u.urlparse(u).path or u
            except ValueError:
                p = u
            citation_count_by_path[p] += 1

    # 結合: page_path をキーに、GA4 と GSC を path レベルで突合
    all_paths: set[str] = set(ga4_map.keys()) | set(gsc_by_path.keys())
    out: list[PagePerformanceRow] = []
    for path in all_paths:
        gsc_v = gsc_by_path.get(path) or {}
        clicks_v = int(gsc_v.get("clicks") or 0)
        impr_v = int(gsc_v.get("impressions") or 0)
        ctr_v = round(clicks_v / impr_v, 4) if impr_v > 0 else None
        out.append(
            PagePerformanceRow(
                page_path=path,
                title=title_by_path.get(path) or title_by_url.get(path),
                sessions=ga4_map.get(path, 0),
                clicks=clicks_v,
                impressions=impr_v,
                ctr=ctr_v,
                avg_position=gsc_v.get("position"),
                citation_count=citation_count_by_path.get(path, 0),
            )
        )
    out.sort(key=lambda r: (r.sessions, r.clicks, r.impressions), reverse=True)
    return out[:limit]


# === 漏斗(問い合わせ → 商談 → 受注)===


class FunnelStage(BaseModel):
    status: str
    count: int
    amount_yen: int  # 受注時のみ意味がある


class FunnelOut(BaseModel):
    period_days: int
    stages: list[FunnelStage]
    cv_rate: float | None  # 受注 / 新規(0〜1)
    avg_amount_yen: float | None
    cpa_yen: float | None  # 顧客獲得単価 = 期間内コンテンツ数 × 仮定単価... ここでは null とし、UI 側で表示しない


@router.get("/funnel", response_model=FunnelOut)
async def funnel(
    days: int = 90,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> FunnelOut:
    from app.db.models.enums import InquiryStatusEnum as _Status
    from app.db.models.inquiry import Inquiry as _Inq

    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    rows = list(
        (
            await session.scalars(
                select(_Inq).where(
                    _Inq.tenant_id == tenant_id,
                    func.date(_Inq.received_at).between(start, end),
                )
            )
        ).all()
    )
    by_status: dict[str, dict] = {
        s.value: {"count": 0, "amount": 0} for s in _Status
    }
    for inq in rows:
        s = inq.status.value
        by_status[s]["count"] += 1
        if inq.amount_yen and s == _Status.contracted.value:
            by_status[s]["amount"] += int(inq.amount_yen)

    new_count = by_status[_Status.new.value]["count"] + by_status[_Status.in_progress.value]["count"] + by_status[_Status.contracted.value]["count"] + by_status[_Status.lost.value]["count"]
    contracted = by_status[_Status.contracted.value]["count"]
    contracted_amount = by_status[_Status.contracted.value]["amount"]

    stages = [
        FunnelStage(status="新規", count=new_count, amount_yen=0),
        FunnelStage(
            status="商談中",
            count=by_status[_Status.in_progress.value]["count"]
            + by_status[_Status.contracted.value]["count"],
            amount_yen=0,
        ),
        FunnelStage(status="受注", count=contracted, amount_yen=contracted_amount),
        FunnelStage(
            status="失注", count=by_status[_Status.lost.value]["count"], amount_yen=0
        ),
    ]
    cv_rate = (contracted / new_count) if new_count > 0 else None
    avg_amt = (contracted_amount / contracted) if contracted > 0 else None
    return FunnelOut(
        period_days=days,
        stages=stages,
        cv_rate=round(cv_rate, 4) if cv_rate is not None else None,
        avg_amount_yen=round(avg_amt, 0) if avg_amt is not None else None,
        cpa_yen=None,
    )


# === キーワード機会マトリクス(impressions × position × 自社引用率)===


class KeywordOpportunity(BaseModel):
    query_text: str
    impressions: int
    avg_position: float | None
    citation_rate: float  # 0〜1
    cluster_id: str | None
    recommended_action: str  # 'win'(順位 1〜3 + 引用も多い)/ 'optimize'(順位 4〜10) / 'create'(impressions 多いが順位なし) / 'monitor'


@router.get("/keyword-opportunity", response_model=list[KeywordOpportunity])
async def keyword_opportunity(
    days: int = 30,
    limit: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[KeywordOpportunity]:
    """検索ボリューム(impressions)と順位、引用率の組み合わせで「次に狙うべきキーワード」を提示。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    gsc_rows = (
        await session.execute(
            select(
                GscQueryMetric.query_text,
                func.sum(GscQueryMetric.impressions).label("imp"),
                func.avg(GscQueryMetric.position).label("pos"),
            )
            .where(
                GscQueryMetric.tenant_id == tenant_id,
                GscQueryMetric.date.between(start, end),
            )
            .group_by(GscQueryMetric.query_text)
            .order_by(func.sum(GscQueryMetric.impressions).desc())
            .limit(limit * 2)
        )
    ).all()

    # 引用率(target_query 単位)
    queries = list(
        (
            await session.scalars(
                select(TargetQuery).where(TargetQuery.tenant_id == tenant_id)
            )
        ).all()
    )
    cluster_by_text = {q.query_text: q.cluster_id for q in queries}
    qid_by_text = {q.query_text: q.id for q in queries}

    citation_rows = list(
        (
            await session.scalars(
                select(CitationLog).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_date.between(start, end),
                )
            )
        ).all()
    )
    cite_by_qid: dict = defaultdict(lambda: [0, 0])
    for c in citation_rows:
        cell = cite_by_qid[c.query_id]
        cell[1] += 1
        if c.self_cited:
            cell[0] += 1

    out: list[KeywordOpportunity] = []
    for r in gsc_rows:
        qt = r.query_text
        imp = int(r.imp or 0)
        pos = float(r.pos) if r.pos is not None else None
        qid = qid_by_text.get(qt)
        cite_pair = cite_by_qid.get(qid, [0, 0]) if qid else [0, 0]
        cite_rate = (cite_pair[0] / cite_pair[1]) if cite_pair[1] > 0 else 0.0

        if pos is None or pos > 30:
            action = "create"  # 露出はあるが順位なし → 新規記事の好機
        elif pos <= 3 and cite_rate >= 0.5:
            action = "win"
        elif pos <= 10:
            action = "optimize"
        else:
            action = "monitor"

        out.append(
            KeywordOpportunity(
                query_text=qt,
                impressions=imp,
                avg_position=round(pos, 1) if pos is not None else None,
                citation_rate=round(cite_rate, 4),
                cluster_id=cluster_by_text.get(qt),
                recommended_action=action,
            )
        )
    return out[:limit]


# === 競合の引用記事の中身分析 ===


class CompetitorContent(BaseModel):
    domain: str
    url: str
    cite_count: int
    sample_query: str | None


@router.get("/competitor-content", response_model=list[CompetitorContent])
async def competitor_content(
    days: int = 30,
    limit: int = 20,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CompetitorContent]:
    """citation_logs から、自社以外のドメインの URL を抽出し引用回数で集計。

    自社 URL 判定: tenants.business_context.site_url ホスト名。
    """
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}
    own_host = ""
    site = bc.get("site_url") or ""
    import urllib.parse as _u

    try:
        own_host = _u.urlparse(site).netloc.lower()
        if own_host.startswith("www."):
            own_host = own_host[4:]
    except ValueError:
        pass

    citations = (
        await session.execute(
            text(
                "SELECT cited_urls, query_id FROM citation_logs "
                "WHERE tenant_id = :tid AND query_date BETWEEN :s AND :e"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    queries = list(
        (
            await session.scalars(
                select(TargetQuery).where(TargetQuery.tenant_id == tenant_id)
            )
        ).all()
    )
    qtext_by_id = {q.id: q.query_text for q in queries}

    # url -> {count, sample_qid}
    by_url: dict[str, dict] = defaultdict(lambda: {"count": 0, "qid": None})
    for row in citations:
        urls = row.cited_urls or []
        if not isinstance(urls, list):
            continue
        for u in urls:
            if not isinstance(u, str) or not u:
                continue
            try:
                host = _u.urlparse(u).netloc.lower()
                if host.startswith("www."):
                    host = host[4:]
            except ValueError:
                continue
            if not host or (own_host and host == own_host):
                continue
            cell = by_url[u]
            cell["count"] += 1
            if cell["qid"] is None:
                cell["qid"] = row.query_id

    items = sorted(by_url.items(), key=lambda x: x[1]["count"], reverse=True)[:limit]
    out: list[CompetitorContent] = []
    for url, v in items:
        try:
            host = _u.urlparse(url).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
        except ValueError:
            host = ""
        out.append(
            CompetitorContent(
                domain=host,
                url=url,
                cite_count=v["count"],
                sample_query=qtext_by_id.get(v["qid"]) if v["qid"] else None,
            )
        )
    return out


# === アラートルール(business_context.alert_rules)===


class AlertRule(BaseModel):
    id: str
    metric: str  # 'sessions_drop_pct' | 'citations_drop_pct' | 'inquiries_zero_days' | 'anomaly'
    threshold: float
    notify_email: str | None = None
    notify_slack_webhook: str | None = None
    enabled: bool = True


@router.get("/alert-rules", response_model=list[AlertRule])
async def get_alert_rules(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AlertRule]:
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}
    raw = bc.get("alert_rules", []) or []
    out: list[AlertRule] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                out.append(AlertRule(**item))
            except Exception:
                continue
    return out


class AlertRulesBulk(BaseModel):
    items: list[AlertRule]


@router.put("/alert-rules", response_model=list[AlertRule])
async def replace_alert_rules(
    body: AlertRulesBulk,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AlertRule]:
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = dict(tenant.business_context or {})
    bc["alert_rules"] = [item.model_dump() for item in body.items]
    tenant.business_context = bc
    await session.commit()
    return body.items


# === A. CV 経路マトリクス(流入元 × LP × CV)===
# 「どのチャネルから来た人が、どのページで、どれくらい問い合わせたか」を
# inquiries.received_at × ai_referrals × ga4_page_daily の同日対応で集計する近似。


class CvPathRow(BaseModel):
    channel: str  # 'AI Chat' | 'Organic Search' | 'Direct/Other'
    sessions: int
    inquiries: int
    cv_rate: float | None  # 0〜1


@router.get("/cv-paths", response_model=list[CvPathRow])
async def cv_paths(
    days: int = 90,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CvPathRow]:
    """流入チャネル別のセッション数と CV 数。inquiries は来訪日が紐付かないため、
    日次セッションで按分して概算する(本格的な multi-touch は GA4 BQ Export が必要)。"""
    from app.db.models.inquiry import Inquiry as _Inq

    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    total_sessions = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(sessions),0) FROM ga4_daily_metrics "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    organic_sessions = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(organic_sessions),0) FROM ga4_daily_metrics "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    ai_sessions = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(sessions),0) FROM ga4_ai_referral_daily "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    other = max(0, total_sessions - organic_sessions - ai_sessions)

    inq_total = (
        await session.scalar(
            select(func.count(_Inq.id)).where(
                _Inq.tenant_id == tenant_id,
                func.date(_Inq.received_at).between(start, end),
            )
        )
    ) or 0
    # チャネル別 inquiries を按分(セッション割合) — 概算用
    def _alloc(sess: int) -> int:
        if total_sessions <= 0:
            return 0
        return round(inq_total * sess / total_sessions)

    rows = [
        ("AI Chat", ai_sessions),
        ("Organic Search", organic_sessions),
        ("Direct/Other", other),
    ]
    out: list[CvPathRow] = []
    for ch, sess in rows:
        cv = _alloc(sess)
        rate = (cv / sess) if sess > 0 else None
        out.append(
            CvPathRow(
                channel=ch,
                sessions=sess,
                inquiries=cv,
                cv_rate=round(rate, 4) if rate is not None else None,
            )
        )
    return out


# === B. 既存記事の順位劣化テーブル ===


class PageRankDecayRow(BaseModel):
    page: str
    title: str | None
    avg_position_recent: float | None
    avg_position_baseline: float | None
    delta: float | None  # baseline - recent. 正なら下落
    impressions_recent: int


@router.get("/page-rank-decay", response_model=list[PageRankDecayRow])
async def page_rank_decay(
    recent_days: int = 14,
    baseline_days: int = 30,  # baseline = 直近 (recent_days+baseline_days) 〜 直近 recent_days の窓
    limit: int = 20,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[PageRankDecayRow]:
    """ページ単位で、直近期間と比較期間の平均順位差を計算。下落が大きい順に返す。"""
    from app.db.models.content import Content as _Content

    await _set_ctx(session, tenant_id)
    end = date.today()
    recent_start = end - timedelta(days=recent_days - 1)
    base_end = recent_start - timedelta(days=1)
    base_start = base_end - timedelta(days=baseline_days - 1)

    # 直近の集計
    recent_rows = (
        await session.execute(
            text(
                "SELECT page, AVG(position) AS pos, COALESCE(SUM(impressions),0) AS imp "
                "FROM gsc_page_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY page"
            ),
            {"tid": str(tenant_id), "s": recent_start, "e": end},
        )
    ).all()
    base_rows = (
        await session.execute(
            text(
                "SELECT page, AVG(position) AS pos FROM gsc_page_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY page"
            ),
            {"tid": str(tenant_id), "s": base_start, "e": base_end},
        )
    ).all()
    base_map = {r.page: float(r.pos) if r.pos is not None else None for r in base_rows}

    contents = list(
        (await session.scalars(select(_Content).where(_Content.tenant_id == tenant_id))).all()
    )
    title_map: dict[str, str] = {}
    import urllib.parse as _u

    for c in contents:
        if c.url:
            title_map[c.url] = c.title or ""
            try:
                p = _u.urlparse(c.url).path
                if p:
                    title_map[p] = c.title or ""
            except ValueError:
                pass

    out: list[PageRankDecayRow] = []
    for r in recent_rows:
        recent_pos = float(r.pos) if r.pos is not None else None
        base_pos = base_map.get(r.page)
        delta = (
            round(recent_pos - base_pos, 1)
            if recent_pos is not None and base_pos is not None
            else None
        )
        try:
            path = _u.urlparse(r.page).path or r.page
        except ValueError:
            path = r.page
        out.append(
            PageRankDecayRow(
                page=r.page,
                title=title_map.get(r.page) or title_map.get(path),
                avg_position_recent=round(recent_pos, 1) if recent_pos is not None else None,
                avg_position_baseline=round(base_pos, 1) if base_pos is not None else None,
                delta=delta,
                impressions_recent=int(r.imp or 0),
            )
        )
    # 下落順(delta が大きい = 順位が悪化)
    out = [o for o in out if o.delta is not None and o.delta > 0]
    out.sort(key=lambda r: (r.delta or 0, r.impressions_recent), reverse=True)
    return out[:limit]


# === C. ブランド検索ボリューム推移 ===


class BrandSearchPoint(BaseModel):
    period: str  # 'YYYY-MM'
    impressions: int
    clicks: int


@router.get("/brand-search", response_model=list[BrandSearchPoint])
async def brand_search(
    months: int = 12,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[BrandSearchPoint]:
    """tenants.business_context.brand_terms または site_url のホスト名から推定したブランド語を含む
    クエリの月次合計。"""
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    bc = tenant.business_context or {}
    brand_terms_raw = bc.get("brand_terms")
    if isinstance(brand_terms_raw, list) and brand_terms_raw:
        terms: list[str] = [str(t).lower() for t in brand_terms_raw if t]
    else:
        # フォールバック: ドメイン名/テナント名から推定
        import contextlib
        import urllib.parse as _u

        site = bc.get("site_url") or ""
        host = ""
        with contextlib.suppress(ValueError):
            host = _u.urlparse(site).netloc.lower().split(".")[0]
        terms = [t for t in [tenant.name.lower() if tenant.name else "", host] if t]

    if not terms:
        return []

    end = date.today()
    start = end - timedelta(days=months * 31)
    like_clauses = " OR ".join([f"LOWER(query_text) LIKE :t{i}" for i in range(len(terms))])
    params: dict = {"tid": str(tenant_id), "s": start, "e": end}
    for i, t in enumerate(terms):
        params[f"t{i}"] = f"%{t}%"
    rows = (
        await session.execute(
            text(
                "SELECT to_char(date, 'YYYY-MM') AS period, "
                "COALESCE(SUM(impressions),0) AS imp, "
                "COALESCE(SUM(clicks),0) AS clk "
                "FROM gsc_query_metrics "
                f"WHERE tenant_id = :tid AND date BETWEEN :s AND :e AND ({like_clauses}) "
                "GROUP BY period ORDER BY period"
            ),
            params,
        )
    ).all()
    return [
        BrandSearchPoint(
            period=r.period, impressions=int(r.imp or 0), clicks=int(r.clk or 0)
        )
        for r in rows
    ]


# === D. 検索意図分類 ===

# ヒューリスティック: クエリのキーワードから意図を推定。
# AI 分類は精度が高いがコストがかかるので、まずキーワード辞書ベース。

_INTENT_RULES: list[tuple[str, list[str]]] = [
    (
        "transactional",
        [
            "おすすめ", "比較", "ランキング", "口コミ", "料金", "価格", "費用",
            "見積", "問い合わせ", "依頼", "発注", "申込", "購入", "業者",
            "会社", "サービス", "事業者", "プロ",
        ],
    ),
    (
        "navigational",
        ["とは何", "とは？", "意味", "違い", "やり方", "方法", "手順", "始め方", "使い方"],
    ),
    (
        "informational",
        [
            "とは", "メリット", "デメリット", "事例", "効果", "活用", "理由",
            "原因", "種類", "一覧",
        ],
    ),
]


def _classify_intent(query: str) -> str:
    q = query.lower()
    for intent, kws in _INTENT_RULES:
        for kw in kws:
            if kw in q:
                return intent
    return "other"


class IntentRow(BaseModel):
    intent: str
    impressions: int
    clicks: int
    queries: int
    avg_position: float | None


@router.get("/search-intent", response_model=list[IntentRow])
async def search_intent(
    days: int = 90,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[IntentRow]:
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    rows = (
        await session.execute(
            select(
                GscQueryMetric.query_text,
                func.sum(GscQueryMetric.impressions).label("imp"),
                func.sum(GscQueryMetric.clicks).label("clk"),
                func.avg(GscQueryMetric.position).label("pos"),
            )
            .where(
                GscQueryMetric.tenant_id == tenant_id,
                GscQueryMetric.date.between(start, end),
            )
            .group_by(GscQueryMetric.query_text)
        )
    ).all()

    by_intent: dict[str, dict] = defaultdict(
        lambda: {"imp": 0, "clk": 0, "n": 0, "pos_sum": 0.0, "pos_n": 0}
    )
    for r in rows:
        intent = _classify_intent(r.query_text or "")
        bucket = by_intent[intent]
        bucket["imp"] += int(r.imp or 0)
        bucket["clk"] += int(r.clk or 0)
        bucket["n"] += 1
        if r.pos is not None:
            bucket["pos_sum"] += float(r.pos)
            bucket["pos_n"] += 1

    out: list[IntentRow] = []
    for intent in ("transactional", "navigational", "informational", "other"):
        v = by_intent.get(intent)
        if not v:
            continue
        avg_pos = (v["pos_sum"] / v["pos_n"]) if v["pos_n"] > 0 else None
        out.append(
            IntentRow(
                intent=intent,
                impressions=v["imp"],
                clicks=v["clk"],
                queries=v["n"],
                avg_position=round(avg_pos, 1) if avg_pos is not None else None,
            )
        )
    return out


# === E. 季節性ヒートマップ(曜日 × 月)===


class SeasonalityCell(BaseModel):
    weekday: int  # 0=月 ... 6=日
    month: int  # 1..12
    avg_sessions: float
    samples: int


@router.get("/seasonality", response_model=list[SeasonalityCell])
async def seasonality(
    months: int = 18,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[SeasonalityCell]:
    """ga4_daily_metrics を曜日 × 月でグルーピングして平均セッションを返す。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=months * 31)
    rows = (
        await session.execute(
            text(
                # PostgreSQL extract: dow=0(日)..6(土)。0=月 表記に変換するため (dow+6)%7
                "SELECT ((EXTRACT(DOW FROM date)::int + 6) % 7) AS weekday, "
                "EXTRACT(MONTH FROM date)::int AS month, "
                "AVG(sessions)::float AS avg_sessions, COUNT(*) AS samples "
                "FROM ga4_daily_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY weekday, month "
                "ORDER BY month, weekday"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    return [
        SeasonalityCell(
            weekday=int(r.weekday),
            month=int(r.month),
            avg_sessions=round(float(r.avg_sessions or 0), 1),
            samples=int(r.samples or 0),
        )
        for r in rows
    ]


# === E1. リファラ Top + 時間別ドリルダウン ===


class ReferralRow(BaseModel):
    source: str
    medium: str
    sessions: int


class ReferralTopOut(BaseModel):
    period_days: int
    total_sessions: int  # 期間内の全セッション(GA4 上の合計、日次から)
    rows: list[ReferralRow]


@router.get("/referrals", response_model=ReferralTopOut)
async def referrals_top(
    days: int = 30,
    limit: int = 15,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ReferralTopOut:
    """指定期間内のリファラ Top N(source / medium 別合計セッション)。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
    rows = (
        await session.execute(
            text(
                "SELECT source, medium, SUM(sessions)::int AS sessions "
                "FROM ga4_referral_daily "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY source, medium "
                "ORDER BY sessions DESC LIMIT :limit"
            ),
            {"tid": str(tenant_id), "s": start, "e": end, "limit": limit},
        )
    ).all()
    total = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(sessions),0) FROM ga4_referral_daily "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    return ReferralTopOut(
        period_days=days,
        total_sessions=total,
        rows=[
            ReferralRow(source=r.source, medium=r.medium, sessions=int(r.sessions))
            for r in rows
        ],
    )


class ReferralHourlyRow(BaseModel):
    hour: int
    source: str
    medium: str
    sessions: int


class ReferralDayDetailOut(BaseModel):
    target_date: date
    total_sessions: int
    daily_breakdown: list[ReferralRow]
    hourly_rows: list[ReferralHourlyRow]


@router.get("/referrals/day", response_model=ReferralDayDetailOut)
async def referrals_day(
    target_date: date,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ReferralDayDetailOut:
    """特定日のリファラ詳細(日合計 + 時間別)。スパイク日の原因特定用。"""
    await _set_ctx(session, tenant_id)
    daily_rows = (
        await session.execute(
            text(
                "SELECT source, medium, sessions FROM ga4_referral_daily "
                "WHERE tenant_id = :tid AND date = :d "
                "ORDER BY sessions DESC"
            ),
            {"tid": str(tenant_id), "d": target_date},
        )
    ).all()
    hourly_rows = (
        await session.execute(
            text(
                "SELECT hour, source, medium, sessions FROM ga4_referral_hourly "
                "WHERE tenant_id = :tid AND date = :d "
                "ORDER BY hour, sessions DESC"
            ),
            {"tid": str(tenant_id), "d": target_date},
        )
    ).all()
    total = sum(int(r.sessions) for r in daily_rows)
    return ReferralDayDetailOut(
        target_date=target_date,
        total_sessions=total,
        daily_breakdown=[
            ReferralRow(source=r.source, medium=r.medium, sessions=int(r.sessions))
            for r in daily_rows
        ],
        hourly_rows=[
            ReferralHourlyRow(
                hour=int(r.hour),
                source=r.source,
                medium=r.medium,
                sessions=int(r.sessions),
            )
            for r in hourly_rows
        ],
    )


# === E2. 曜日 × 時間帯ヒートマップ(GA4 hourly) ===


class HourWeekdayCell(BaseModel):
    weekday: int  # 0=月 ... 6=日
    hour: int  # 0〜23
    sessions: int  # 期間内のこの (曜日, 時間帯) のセッション総数


class HourWeekdayHeatmapOut(BaseModel):
    period_days: int
    cells: list[HourWeekdayCell]
    peaks: list[HourWeekdayCell]


@router.get("/hour-weekday-heatmap", response_model=HourWeekdayHeatmapOut)
async def hour_weekday_heatmap(
    days: int = 90,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> HourWeekdayHeatmapOut:
    """ga4_hourly_metrics を (曜日 × 時間帯) でグルーピングし、
    指定期間内のセッション総数を返す。
    """
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    rows = (
        await session.execute(
            text(
                "SELECT ((EXTRACT(DOW FROM date)::int + 6) % 7) AS weekday, "
                "hour, "
                "SUM(sessions)::int AS sessions "
                "FROM ga4_hourly_metrics "
                "WHERE tenant_id = :tid AND date BETWEEN :s AND :e "
                "GROUP BY weekday, hour "
                "ORDER BY weekday, hour"
            ),
            {"tid": str(tenant_id), "s": start, "e": end},
        )
    ).all()
    cells = [
        HourWeekdayCell(
            weekday=int(r.weekday),
            hour=int(r.hour),
            sessions=int(r.sessions or 0),
        )
        for r in rows
    ]
    peaks = sorted(cells, key=lambda c: c.sessions, reverse=True)[:5]
    return HourWeekdayHeatmapOut(period_days=days, cells=cells, peaks=peaks)


# === F. エリア別パフォーマンス ===


class AreaPerformance(BaseModel):
    cluster_id: str
    impressions: int
    clicks: int
    avg_position: float | None
    citation_rate: float
    queries: int


@router.get("/area-performance", response_model=list[AreaPerformance])
async def area_performance(
    days: int = 90,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AreaPerformance]:
    """target_queries.cluster_id ごとに impressions/clicks/順位/AI 引用率を集計。
    地域戦略(local_district_hq / local_radius / geo_intent / industry_local)の検証に使う。"""
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    queries = list(
        (
            await session.scalars(
                select(TargetQuery).where(TargetQuery.tenant_id == tenant_id)
            )
        ).all()
    )
    if not queries:
        return []
    cluster_by_text = {q.query_text: q.cluster_id or "unknown" for q in queries}
    qid_by_text = {q.query_text: q.id for q in queries}

    # GSC は target_queries 限定で集計
    query_texts = list(cluster_by_text.keys())
    if not query_texts:
        return []
    gsc_rows = (
        await session.execute(
            select(
                GscQueryMetric.query_text,
                func.sum(GscQueryMetric.impressions).label("imp"),
                func.sum(GscQueryMetric.clicks).label("clk"),
                func.avg(GscQueryMetric.position).label("pos"),
            )
            .where(
                GscQueryMetric.tenant_id == tenant_id,
                GscQueryMetric.date.between(start, end),
                GscQueryMetric.query_text.in_(query_texts),
            )
            .group_by(GscQueryMetric.query_text)
        )
    ).all()

    citation_rows = list(
        (
            await session.scalars(
                select(CitationLog).where(
                    CitationLog.tenant_id == tenant_id,
                    CitationLog.query_date.between(start, end),
                )
            )
        ).all()
    )
    cite_by_qid: dict = defaultdict(lambda: [0, 0])
    for c in citation_rows:
        cell = cite_by_qid[c.query_id]
        cell[1] += 1
        if c.self_cited:
            cell[0] += 1

    by_cluster: dict[str, dict] = defaultdict(
        lambda: {"imp": 0, "clk": 0, "pos_sum": 0.0, "pos_n": 0, "cite_self": 0, "cite_total": 0, "n": 0}
    )
    for r in gsc_rows:
        cluster = cluster_by_text.get(r.query_text or "", "unknown")
        b = by_cluster[cluster]
        b["imp"] += int(r.imp or 0)
        b["clk"] += int(r.clk or 0)
        if r.pos is not None:
            b["pos_sum"] += float(r.pos) * int(r.imp or 0)
            b["pos_n"] += int(r.imp or 0)
        b["n"] += 1
        qid = qid_by_text.get(r.query_text or "")
        if qid:
            cite = cite_by_qid.get(qid, [0, 0])
            b["cite_self"] += cite[0]
            b["cite_total"] += cite[1]

    out: list[AreaPerformance] = []
    for cluster, v in by_cluster.items():
        avg_pos = (v["pos_sum"] / v["pos_n"]) if v["pos_n"] > 0 else None
        rate = (v["cite_self"] / v["cite_total"]) if v["cite_total"] > 0 else 0.0
        out.append(
            AreaPerformance(
                cluster_id=cluster,
                impressions=v["imp"],
                clicks=v["clk"],
                avg_position=round(avg_pos, 1) if avg_pos is not None else None,
                citation_rate=round(rate, 4),
                queries=v["n"],
            )
        )
    out.sort(key=lambda r: r.impressions, reverse=True)
    return out


# === G. PageSpeed Insights 直近結果 ===


class PageSpeedRow(BaseModel):
    page_url: str
    strategy: str
    performance_score: int | None
    lcp_ms: int | None
    cls: float | None
    inp_ms: int | None
    measured_at: date


@router.get("/page-speed", response_model=list[PageSpeedRow])
async def page_speed(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[PageSpeedRow]:
    """各 URL × strategy の最新計測結果を返す。"""
    await _set_ctx(session, tenant_id)
    rows = (
        await session.execute(
            text(
                "SELECT DISTINCT ON (page_url, strategy) "
                "page_url, strategy, performance_score, lcp_ms, cls, inp_ms, date "
                "FROM page_speed_metrics "
                "WHERE tenant_id = :tid "
                "ORDER BY page_url, strategy, date DESC"
            ),
            {"tid": str(tenant_id)},
        )
    ).all()
    return [
        PageSpeedRow(
            page_url=r.page_url,
            strategy=r.strategy,
            performance_score=r.performance_score,
            lcp_ms=r.lcp_ms,
            cls=float(r.cls) if r.cls is not None else None,
            inp_ms=r.inp_ms,
            measured_at=r.date,
        )
        for r in rows
    ]


# === チャネル別 CVR(セッション × 実測問い合わせソース)===


class ChannelCvrRow(BaseModel):
    channel: str  # 'AI Chat' / 'Organic Search' / 'Direct/Other'
    sessions: int
    inquiries: int
    cvr: float | None  # 0〜1。問い合わせ ÷ セッション


@router.get("/channel-cvr", response_model=list[ChannelCvrRow])
async def channel_cvr(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChannelCvrRow]:
    """流入チャネル別の CVR(問い合わせ ÷ セッション)。

    チャネル定義(GA4 ベース):
    - AI Chat:  ga4_ai_referral_daily.sessions の合計
    - Organic Search: ga4_daily_metrics.organic_sessions の合計
    - Direct/Other: 全セッション − Organic − AI

    問い合わせ側は inquiries.source_channel を使い、AI 由来 (source_channel='ai')、
    web 経由 (source_channel='web')、その他 (email/phone/other) で振り分ける。
    web の内訳(Organic/Direct)は流入比で按分する。
    """
    from app.db.models.enums import InquirySourceEnum as _Src
    from app.db.models.inquiry import Inquiry as _Inq

    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)

    total_sessions = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(sessions),0) FROM ga4_daily_metrics "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    organic_sessions = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(organic_sessions),0) FROM ga4_daily_metrics "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    ai_sessions = int(
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(sessions),0) FROM ga4_ai_referral_daily "
                    "WHERE tenant_id = :tid AND date BETWEEN :s AND :e"
                ),
                {"tid": str(tenant_id), "s": start, "e": end},
            )
        ).scalar()
        or 0
    )
    other_sessions = max(0, total_sessions - organic_sessions - ai_sessions)

    # 問い合わせをソース別に集計
    inq_rows = (
        await session.execute(
            select(_Inq.source_channel, func.count(_Inq.id)).where(
                _Inq.tenant_id == tenant_id,
                func.date(_Inq.received_at).between(start, end),
            ).group_by(_Inq.source_channel)
        )
    ).all()
    inq_by_src: dict[str, int] = {r[0].value: int(r[1] or 0) for r in inq_rows}
    inq_ai = inq_by_src.get(_Src.ai.value, 0)
    inq_web = inq_by_src.get(_Src.web.value, 0)
    # email/phone/other は Direct/Other に寄せる
    inq_other_direct = (
        inq_by_src.get(_Src.email.value, 0)
        + inq_by_src.get(_Src.phone.value, 0)
        + inq_by_src.get(_Src.other.value, 0)
    )

    # web 由来の問い合わせを Organic と Direct/Other に流入比で按分
    web_session_base = organic_sessions + other_sessions
    if web_session_base > 0:
        inq_organic = round(inq_web * organic_sessions / web_session_base)
        inq_direct = inq_web - inq_organic + inq_other_direct
    else:
        inq_organic = 0
        inq_direct = inq_web + inq_other_direct

    def _rate(c: int, s: int) -> float | None:
        if s <= 0:
            return None
        return round(c / s, 4)

    return [
        ChannelCvrRow(
            channel="AI Chat",
            sessions=ai_sessions,
            inquiries=inq_ai,
            cvr=_rate(inq_ai, ai_sessions),
        ),
        ChannelCvrRow(
            channel="Organic Search",
            sessions=organic_sessions,
            inquiries=inq_organic,
            cvr=_rate(inq_organic, organic_sessions),
        ),
        ChannelCvrRow(
            channel="Direct/Other",
            sessions=other_sessions,
            inquiries=inq_direct,
            cvr=_rate(inq_direct, other_sessions),
        ),
    ]


# === クエリ順位変動 Top N(上昇 / 下落)===


class QueryRankChangeRow(BaseModel):
    query_text: str
    avg_position_recent: float | None
    avg_position_prev: float | None
    delta: float | None  # prev - recent。正なら順位が上昇(数字が小さくなる方向)
    impressions_recent: int
    clicks_recent: int


class QueryRankChangesOut(BaseModel):
    period_days: int
    rising: list[QueryRankChangeRow]  # 上昇(delta が大きい順)
    falling: list[QueryRankChangeRow]  # 下落(delta が小さい順)


@router.get("/query-rank-changes", response_model=QueryRankChangesOut)
async def query_rank_changes(
    days: int = 14,
    limit: int = 10,
    min_impressions: int = 50,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> QueryRankChangesOut:
    """直近 N 日と前 N 日でクエリ別平均順位の差分を計算し、上昇/下落の Top を返す。

    - delta = prev - recent。プラス = 順位が上がった、マイナス = 下がった。
    - 直近期間に min_impressions 未満のクエリは除外(ノイズ抑制)。
    """
    await _set_ctx(session, tenant_id)
    end = date.today()
    recent_start = end - timedelta(days=days - 1)
    prev_end = recent_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    rows = (
        await session.execute(
            text(
                """
                WITH recent AS (
                    SELECT query_text,
                           AVG(position) AS pos,
                           SUM(impressions) AS impr,
                           SUM(clicks) AS clk
                    FROM gsc_query_metrics
                    WHERE tenant_id = :tid AND date BETWEEN :rs AND :re
                    GROUP BY query_text
                ), prev AS (
                    SELECT query_text,
                           AVG(position) AS pos,
                           SUM(impressions) AS impr
                    FROM gsc_query_metrics
                    WHERE tenant_id = :tid AND date BETWEEN :ps AND :pe
                    GROUP BY query_text
                )
                SELECT r.query_text,
                       r.pos AS recent_pos,
                       p.pos AS prev_pos,
                       r.impr AS recent_impr,
                       r.clk AS recent_clk
                FROM recent r
                JOIN prev p USING (query_text)
                WHERE r.impr >= :min_impr
                  AND p.pos IS NOT NULL
                  AND r.pos IS NOT NULL
                """
            ),
            {
                "tid": str(tenant_id),
                "rs": recent_start,
                "re": end,
                "ps": prev_start,
                "pe": prev_end,
                "min_impr": min_impressions,
            },
        )
    ).all()

    items = []
    for r in rows:
        recent_pos = float(r.recent_pos) if r.recent_pos is not None else None
        prev_pos = float(r.prev_pos) if r.prev_pos is not None else None
        delta = (
            round(prev_pos - recent_pos, 2)
            if (recent_pos is not None and prev_pos is not None)
            else None
        )
        items.append(
            QueryRankChangeRow(
                query_text=r.query_text,
                avg_position_recent=round(recent_pos, 2) if recent_pos is not None else None,
                avg_position_prev=round(prev_pos, 2) if prev_pos is not None else None,
                delta=delta,
                impressions_recent=int(r.recent_impr or 0),
                clicks_recent=int(r.recent_clk or 0),
            )
        )

    rising = sorted(
        [i for i in items if i.delta is not None and i.delta > 0],
        key=lambda x: (x.delta or 0),
        reverse=True,
    )[:limit]
    falling = sorted(
        [i for i in items if i.delta is not None and i.delta < 0],
        key=lambda x: (x.delta or 0),
    )[:limit]
    return QueryRankChangesOut(
        period_days=days, rising=rising, falling=falling
    )


# === データソース一覧(各ブロックの「いつのデータか」表示用)===


class DataSourceInfo(BaseModel):
    """1 データソース(=テーブル相当)の情報。"""

    key: str  # フロントが参照するキー(例: 'ga4_daily', 'gsc_query', 'inquiries')
    label: str  # 表示名(例: 'GA4 日次', 'GSC クエリ')
    provider: str  # 'GA4' / 'GSC' / '内部DB' / 'PageSpeed' / 'AI Engine'
    coverage_from: date | None  # 最古日付
    coverage_to: date | None  # 最新日付
    row_count: int  # 行数
    last_job_at: datetime | None  # 最終収集ジョブ成功時刻
    job_name: str | None  # 紐付くジョブ名


@router.get("/data-sources", response_model=dict[str, DataSourceInfo])
async def data_sources(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, DataSourceInfo]:
    """ダッシュボード各ブロックが依存するデータソースの最新状態を一覧で返す。

    フロント側は要素ごとに必要なキーをルックアップして「いつのデータか」を表示する。
    """
    await _set_ctx(session, tenant_id)

    # 主要テーブル定義: (キー, ラベル, プロバイダ, テーブル名, 日付カラム, 紐付くジョブ名)
    sources: list[tuple[str, str, str, str, str, str | None]] = [
        ("ga4_daily", "GA4 日次", "GA4", "ga4_daily_metrics", "date", "collect_ga4"),
        ("ga4_hourly", "GA4 時間別", "GA4", "ga4_hourly_metrics", "date", "collect_ga4"),
        ("ga4_page", "GA4 ページ別", "GA4", "ga4_page_daily", "date", "collect_ga4"),
        (
            "ga4_referral",
            "GA4 リファラ",
            "GA4",
            "ga4_referral_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_referral_hourly",
            "GA4 リファラ時間別",
            "GA4",
            "ga4_referral_hourly",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_ai_referral",
            "GA4 AI 流入",
            "GA4",
            "ga4_ai_referral_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_ai_referral_event",
            "GA4 AI 流入(イベント)",
            "GA4",
            "ga4_ai_referral_event_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_ai_crawler",
            "GA4 AI クローラー",
            "GA4",
            "ga4_ai_crawler_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_ai_crawler_page",
            "GA4 AI クローラー(ページ別)",
            "GA4",
            "ga4_ai_crawler_page_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_llms_txt",
            "GA4 llms.txt 取得",
            "GA4",
            "ga4_llms_txt_fetch_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_article_read",
            "GA4 完読",
            "GA4",
            "ga4_article_read_complete_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_text_copy",
            "GA4 本文コピー",
            "GA4",
            "ga4_text_copy_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_outbound",
            "GA4 外部リンク",
            "GA4",
            "ga4_outbound_click_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_cta",
            "GA4 CTA クリック",
            "GA4",
            "ga4_cta_click_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_tool_use",
            "GA4 ツール利用",
            "GA4",
            "ga4_tool_use_daily",
            "date",
            "collect_ga4",
        ),
        (
            "ga4_engagement",
            "GA4 エンゲージ補助",
            "GA4",
            "ga4_engagement_signal_daily",
            "date",
            "collect_ga4",
        ),
        ("gsc_page", "GSC ページ", "GSC", "gsc_page_metrics", "date", "collect_gsc"),
        ("gsc_query", "GSC クエリ", "GSC", "gsc_query_metrics", "date", "collect_gsc"),
        (
            "citation",
            "AI 引用ログ",
            "AI モニタ",
            "citation_logs",
            "query_date",
            "monitor_citation",
        ),
        (
            "inquiries",
            "問い合わせ",
            "内部DB",
            "inquiries",
            "received_at::date",
            None,
        ),
        (
            "contents",
            "公開記事",
            "内部DB",
            "contents",
            "published_at::date",
            None,
        ),
        (
            "marketing_actions",
            "施策タイムライン",
            "内部DB",
            "marketing_actions",
            "action_date",
            None,
        ),
        (
            "page_speed",
            "PageSpeed",
            "PageSpeed",
            "page_speed_metrics",
            "date",
            "collect_pagespeed",
        ),
        (
            "competitor_post",
            "競合投稿",
            "RSS",
            "competitor_posts",
            "published_at::date",
            "collect_competitor_rss",
        ),
    ]

    # ジョブ最終成功時刻を一括取得
    job_rows = (
        await session.execute(
            text(
                "SELECT job_name, MAX(finished_at) AS last_at FROM job_execution_logs "
                "WHERE (tenant_id = :tid OR tenant_id IS NULL) AND status = 'success' "
                "GROUP BY job_name"
            ),
            {"tid": str(tenant_id)},
        )
    ).all()
    last_job_by_name = {r.job_name: r.last_at for r in job_rows}

    out: dict[str, DataSourceInfo] = {}
    for key, label, provider, table, date_col, job_name in sources:
        # contents は status='published' のみカバレッジ集計
        where_clause = "tenant_id = :tid"
        if table == "contents":
            where_clause += " AND status = 'published' AND published_at IS NOT NULL"
        try:
            row = (
                await session.execute(
                    text(
                        f"SELECT MIN({date_col}) AS mn, MAX({date_col}) AS mx, "
                        f"COUNT(*) AS cnt FROM {table} WHERE {where_clause}"
                    ),
                    {"tid": str(tenant_id)},
                )
            ).one()
            mn = row.mn
            mx = row.mx
            cnt = int(row.cnt or 0)
        except Exception:
            mn = mx = None
            cnt = 0
        out[key] = DataSourceInfo(
            key=key,
            label=label,
            provider=provider,
            coverage_from=mn,
            coverage_to=mx,
            row_count=cnt,
            last_job_at=last_job_by_name.get(job_name) if job_name else None,
            job_name=job_name,
        )
    return out
