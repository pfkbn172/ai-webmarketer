"""Phase 2 戦略思考レイヤー API。

/strategic/review        : 単発の戦略レビュー実行
/strategic/probe-loop    : 戦略軸 A/B の比較評価
/strategic/competitor-patterns : 競合パターン分析(citation_logs 頻出ドメイン)
/strategic/anomalies     : 違和感検知の現状確認
/strategic/content/{id}/improve : 記事改善提案
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.usecases.content_improvement import improve_content
from app.ai_engine.usecases.probe_loop import compare_strategy_axes
from app.ai_engine.usecases.strategic_review import run_strategic_review
from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.services.anomaly_detector import detect as detect_anomalies
from app.services.competitor_analysis import analyze_competitor_patterns

router = APIRouter(prefix="/strategic", tags=["strategic"])


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


class AnomalyOut(BaseModel):
    kind: str
    detail: str
    severity: str


@router.get("/anomalies", response_model=list[AnomalyOut])
async def get_anomalies(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AnomalyOut]:
    await _set_ctx(session, tenant_id)
    items = await detect_anomalies(session, tenant_id)
    return [AnomalyOut(kind=a.kind, detail=a.detail, severity=a.severity) for a in items]


@router.post("/review")
async def post_review(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _set_ctx(session, tenant_id)
    return await run_strategic_review(session, tenant_id)


@router.post("/probe-loop")
async def post_probe_loop(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _set_ctx(session, tenant_id)
    return await compare_strategy_axes(session, tenant_id)


class CompetitorPattern(BaseModel):
    domain: str
    count: int
    label: str  # 'candidate' | 'registered_competitor' | 'excluded'


@router.get("/competitor-patterns", response_model=list[CompetitorPattern])
async def get_competitor_patterns(
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CompetitorPattern]:
    await _set_ctx(session, tenant_id)
    items = await analyze_competitor_patterns(session, tenant_id, lookback_days=days)
    return [CompetitorPattern(**i) for i in items]


@router.post("/content/{content_id}/improve")
async def post_improve_content(
    content_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _set_ctx(session, tenant_id)
    try:
        return await improve_content(session, tenant_id, content_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
