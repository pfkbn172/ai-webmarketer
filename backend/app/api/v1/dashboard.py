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
from datetime import date, timedelta

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


# === 記事/ページ単位のパフォーマンス ===

# GA4 の pagePath(/blog/foo) と GSC の page(完全 URL)を URL の path 部分でつなぐ。
# 完全一致しない場合は path で結合する。


class PagePerformanceRow(BaseModel):
    page_path: str
    title: str | None
    sessions: int
    clicks: int
    impressions: int
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
        out.append(
            PagePerformanceRow(
                page_path=path,
                title=title_by_path.get(path) or title_by_url.get(path),
                sessions=ga4_map.get(path, 0),
                clicks=int(gsc_v.get("clicks") or 0),
                impressions=int(gsc_v.get("impressions") or 0),
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
