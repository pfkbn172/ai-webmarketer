"""キーワードユニバース API。

GET  /keyword-universe          一覧(クラスタ/最低スコア/上限件数で絞込)
POST /keyword-universe/refresh  手動で集計ジョブを起動
GET  /keyword-universe/clusters クラスタ別件数(タブ表示用)
"""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.keyword_universe import KeywordUniverse
from app.keyword_engine.aggregator import aggregate_universe

router = APIRouter(prefix="/keyword-universe", tags=["keyword_universe"])


class KeywordUniverseOut(BaseModel):
    id: uuid.UUID
    keyword: str
    cluster_ids: list[str]
    intent: str | None
    is_geographic: bool
    gsc_imp_12m: int
    gsc_clicks_12m: int
    gsc_avg_position: Decimal | None
    suggest_derivative_count: int
    competitor_coverage_count: int
    llm_self_cite_rate: Decimal | None
    llm_competitor_cite_rate: Decimal | None
    priority_score: Decimal
    opportunity_flag: str | None
    source_breakdown: dict[str, Any]


class ClusterCount(BaseModel):
    cluster_id: str
    rows: int


class RefreshResult(BaseModel):
    upserted: int


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("", response_model=list[KeywordUniverseOut])
async def list_universe(
    cluster_id: str | None = Query(None, description="絞込みクラスタID"),
    min_priority: float = Query(0.0, ge=0, description="最低 priority_score"),
    opportunity_flag: str | None = Query(
        None, description="opportunity_flag フィルタ('high_demand_no_coverage' 等)"
    ),
    limit: int = Query(200, ge=1, le=1000, description="最大件数"),
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[KeywordUniverseOut]:
    await _set_ctx(session, tenant_id)

    stmt = select(KeywordUniverse).where(
        KeywordUniverse.tenant_id == tenant_id,
        KeywordUniverse.priority_score >= min_priority,
    )
    if cluster_id:
        # text[] 上の包含演算 @>
        stmt = stmt.where(KeywordUniverse.cluster_ids.contains([cluster_id]))
    if opportunity_flag:
        stmt = stmt.where(KeywordUniverse.opportunity_flag == opportunity_flag)
    stmt = stmt.order_by(desc(KeywordUniverse.priority_score)).limit(limit)

    rows = list((await session.scalars(stmt)).all())
    return [
        KeywordUniverseOut(
            id=r.id,
            keyword=r.keyword,
            cluster_ids=list(r.cluster_ids or []),
            intent=r.intent,
            is_geographic=r.is_geographic,
            gsc_imp_12m=r.gsc_imp_12m,
            gsc_clicks_12m=r.gsc_clicks_12m,
            gsc_avg_position=r.gsc_avg_position,
            suggest_derivative_count=r.suggest_derivative_count,
            competitor_coverage_count=r.competitor_coverage_count,
            llm_self_cite_rate=r.llm_self_cite_rate,
            llm_competitor_cite_rate=r.llm_competitor_cite_rate,
            priority_score=r.priority_score,
            opportunity_flag=r.opportunity_flag,
            source_breakdown=r.source_breakdown or {},
        )
        for r in rows
    ]


@router.get("/clusters", response_model=list[ClusterCount])
async def cluster_counts(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ClusterCount]:
    """各 cluster_id ごとの行数(タブ件数バッジ用)。
    cluster_ids text[] を unnest して GROUP BY する。
    """
    await _set_ctx(session, tenant_id)
    stmt = (
        select(
            func.unnest(KeywordUniverse.cluster_ids).label("cid"),
            func.count().label("rows"),
        )
        .where(KeywordUniverse.tenant_id == tenant_id)
        .group_by(text("cid"))
        .order_by(desc(text("rows")))
    )
    res = await session.execute(stmt)
    return [ClusterCount(cluster_id=cid, rows=int(rows)) for cid, rows in res]


@router.post("/refresh", response_model=RefreshResult)
async def refresh_universe(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> RefreshResult:
    """同期で集計ジョブを実行する(数秒程度)。"""
    n = await aggregate_universe(session, tenant_id)
    return RefreshResult(upserted=n)
