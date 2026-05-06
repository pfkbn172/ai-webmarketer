"""ホーム画面用 API。

GET /home/today
  オーナーが朝開く1画面に必要な情報をまとめて返す:
    - 今日の3アクション(daily_actions の最新生成)
    - 今週のKPI(AI流入セッション/自社引用率/問い合わせ件数/機会数)
    - システム健全性(直近24時間のジョブ失敗)
    - 最近の更新(ブリーフ/レポート/再集計など)
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.citation_log import CitationLog
from app.db.models.content_brief import ContentBrief
from app.db.models.daily_action import DailyAction
from app.db.models.enums import JobStatusEnum
from app.db.models.ga4_ai_referral_daily import Ga4AiReferralDaily
from app.db.models.inquiry import Inquiry
from app.db.models.job_execution_log import JobExecutionLog
from app.db.models.keyword_universe import KeywordUniverse

router = APIRouter(prefix="/home", tags=["home"])


class TodayAction(BaseModel):
    id: uuid.UUID
    action_index: int
    severity: str  # 'red' | 'yellow' | 'green'
    title: str
    rationale: str | None
    target_url: str | None
    related_keyword: str | None
    generated_at: datetime


class KpiSummary(BaseModel):
    ai_referral_sessions_7d: int
    ai_referral_sessions_prev_7d: int
    self_cite_rate_30d: float | None
    inquiries_30d: int
    opportunity_count: int


class HealthIssue(BaseModel):
    job_name: str
    severity: str  # 'warning' | 'error'
    message: str
    target_url: str | None = None


class RecentUpdate(BaseModel):
    kind: str  # 'brief' | 'aggregate' | 'job'
    title: str
    when: datetime
    target_url: str | None = None


class HomeTodayOut(BaseModel):
    actions: list[TodayAction]
    kpi: KpiSummary
    health: list[HealthIssue]
    recent_updates: list[RecentUpdate]
    actions_generated_at: datetime | None
    actions_stale: bool  # 24時間以上更新がない=true


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/today", response_model=HomeTodayOut)
async def home_today(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> HomeTodayOut:
    await _set_ctx(session, tenant_id)
    now = datetime.now(UTC)

    # ---- 今日の3アクション(最新生成バッチ) ----
    latest_action = (
        await session.scalars(
            select(DailyAction)
            .where(DailyAction.tenant_id == tenant_id)
            .order_by(desc(DailyAction.generated_at))
            .limit(1)
        )
    ).one_or_none()

    actions: list[TodayAction] = []
    actions_generated_at: datetime | None = None
    actions_stale = True
    if latest_action:
        actions_generated_at = latest_action.generated_at
        actions_stale = (now - latest_action.generated_at) > timedelta(hours=24)
        rows = list(
            (
                await session.scalars(
                    select(DailyAction)
                    .where(
                        DailyAction.tenant_id == tenant_id,
                        DailyAction.generated_at == latest_action.generated_at,
                    )
                    .order_by(DailyAction.action_index)
                )
            ).all()
        )
        actions = [
            TodayAction(
                id=r.id,
                action_index=r.action_index,
                severity=r.severity,
                title=r.title,
                rationale=r.rationale,
                target_url=r.target_url,
                related_keyword=r.related_keyword,
                generated_at=r.generated_at,
            )
            for r in rows
        ]

    # ---- KPI(AI流入7日 / 引用率30日 / 問合せ30日 / 機会数) ----
    seven_days_ago = (now - timedelta(days=7)).date()
    fourteen_days_ago = (now - timedelta(days=14)).date()
    thirty_days_ago = (now - timedelta(days=30)).date()

    ai_session_curr = (
        await session.scalar(
            select(func.coalesce(func.sum(Ga4AiReferralDaily.sessions), 0))
            .where(
                Ga4AiReferralDaily.tenant_id == tenant_id,
                Ga4AiReferralDaily.date >= seven_days_ago,
            )
        )
    ) or 0
    ai_session_prev = (
        await session.scalar(
            select(func.coalesce(func.sum(Ga4AiReferralDaily.sessions), 0))
            .where(
                Ga4AiReferralDaily.tenant_id == tenant_id,
                Ga4AiReferralDaily.date >= fourteen_days_ago,
                Ga4AiReferralDaily.date < seven_days_ago,
            )
        )
    ) or 0

    cite_total = (
        await session.scalar(
            select(func.count(CitationLog.id)).where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date >= thirty_days_ago,
            )
        )
    ) or 0
    cite_self = (
        await session.scalar(
            select(func.count(CitationLog.id)).where(
                CitationLog.tenant_id == tenant_id,
                CitationLog.query_date >= thirty_days_ago,
                CitationLog.self_cited.is_(True),
            )
        )
    ) or 0
    self_cite_rate = round(cite_self / cite_total, 4) if cite_total else None

    inquiries_count = (
        await session.scalar(
            select(func.count(Inquiry.id)).where(
                Inquiry.tenant_id == tenant_id,
                Inquiry.created_at >= now - timedelta(days=30),
            )
        )
    ) or 0

    opp_count = (
        await session.scalar(
            select(func.count(KeywordUniverse.id)).where(
                KeywordUniverse.tenant_id == tenant_id,
                KeywordUniverse.opportunity_flag == "high_demand_no_coverage",
            )
        )
    ) or 0

    # ---- システム健全性(直近24時間に failed があれば warning) ----
    issues: list[HealthIssue] = []
    cutoff = now - timedelta(hours=24)
    failed_jobs = list(
        (
            await session.scalars(
                select(JobExecutionLog)
                .where(
                    JobExecutionLog.tenant_id == tenant_id,
                    JobExecutionLog.status == JobStatusEnum.failed,
                    JobExecutionLog.started_at >= cutoff,
                )
                .order_by(desc(JobExecutionLog.started_at))
            )
        ).all()
    )
    seen_jobs: set[str] = set()
    for j in failed_jobs:
        if j.job_name in seen_jobs:
            continue
        seen_jobs.add(j.job_name)
        target = "/settings/status"
        if j.job_name in ("collect_gsc", "collect_ga4", "collect_pagespeed"):
            target = "/settings/credentials"
        issues.append(
            HealthIssue(
                job_name=j.job_name,
                severity="error",
                message=f"{j.job_name} が失敗しています",
                target_url=target,
            )
        )

    # CV未設定警告(GA4 conversions が直近30日0)
    if inquiries_count == 0:
        from sqlalchemy import select as _sel
        from app.db.models.ga4_daily_metric import Ga4DailyMetric

        ga4_cv = (
            await session.scalar(
                _sel(func.coalesce(func.sum(Ga4DailyMetric.conversions), 0)).where(
                    Ga4DailyMetric.tenant_id == tenant_id,
                    Ga4DailyMetric.date >= thirty_days_ago,
                )
            )
        ) or 0
        if ga4_cv == 0:
            issues.append(
                HealthIssue(
                    job_name="ga4_conversion",
                    severity="warning",
                    message="GA4 のコンバージョン計測が未設定です(直近30日のCV=0)",
                    target_url="/settings/manual",
                )
            )

    # ---- 最近の更新(ブリーフ/レポート/再集計など) ----
    recent: list[RecentUpdate] = []
    for b in list(
        (
            await session.scalars(
                select(ContentBrief)
                .where(ContentBrief.tenant_id == tenant_id)
                .order_by(desc(ContentBrief.created_at))
                .limit(3)
            )
        ).all()
    ):
        recent.append(
            RecentUpdate(
                kind="brief",
                title=f"ブリーフ「{b.title[:30]}…」",
                when=b.created_at,
                target_url=f"/production/briefs/{b.id}",
            )
        )

    # 最新の集計ジョブ完了
    last_agg = (
        await session.scalars(
            select(JobExecutionLog)
            .where(
                JobExecutionLog.tenant_id == tenant_id,
                JobExecutionLog.job_name == "aggregate_keyword_universe",
                JobExecutionLog.status == JobStatusEnum.success,
            )
            .order_by(desc(JobExecutionLog.started_at))
            .limit(1)
        )
    ).one_or_none()
    if last_agg and last_agg.finished_at:
        recent.append(
            RecentUpdate(
                kind="aggregate",
                title="キーワードユニバースを再集計しました",
                when=last_agg.finished_at,
                target_url="/strategy/universe",
            )
        )

    recent.sort(key=lambda r: r.when, reverse=True)
    recent = recent[:5]

    return HomeTodayOut(
        actions=actions,
        kpi=KpiSummary(
            ai_referral_sessions_7d=int(ai_session_curr),
            ai_referral_sessions_prev_7d=int(ai_session_prev),
            self_cite_rate_30d=float(self_cite_rate) if self_cite_rate is not None else None,
            inquiries_30d=int(inquiries_count),
            opportunity_count=int(opp_count),
        ),
        health=issues,
        recent_updates=recent,
        actions_generated_at=actions_generated_at,
        actions_stale=actions_stale,
    )


class RegenerateResult(BaseModel):
    count: int


@router.post("/today/regenerate", response_model=RegenerateResult)
async def regenerate_today(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> RegenerateResult:
    """同期で今日のアクションを再生成する(数秒〜十数秒)。"""
    from app.ai_engine.usecases.daily_action import recommend_daily_actions

    await _set_ctx(session, tenant_id)
    actions = await recommend_daily_actions(session, tenant_id)
    return RegenerateResult(count=len(actions))
