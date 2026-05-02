"""引用モニタの手入力 API。

API キー未契約の LLM(ChatGPT/Claude/Perplexity/AIO 等)について、
ユーザーが LLM の Web 版で実際に検索した結果を貼り付けて記録するための API。
保存時に matcher.evaluate() を通して self_cited / competitor_cited を自動判定する。
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.collectors.llm_citation.matcher import MatchProfile, evaluate
from app.db.base import get_db_session
from app.db.models.citation_log import CitationLog
from app.db.models.competitor import Competitor
from app.db.models.enums import LLMProviderEnum
from app.db.models.target_query import TargetQuery
from app.db.models.tenant import Tenant

router = APIRouter(prefix="/citation-logs/manual", tags=["citation_manual"])


class ManualCitationIn(BaseModel):
    query_id: uuid.UUID
    llm_provider: LLMProviderEnum
    response_text: str = Field(min_length=1, max_length=20000)
    cited_urls: list[str] = []
    query_date: date | None = None  # 未指定なら今日


class ManualCitationOut(BaseModel):
    id: uuid.UUID
    self_cited: bool
    self_match_reason: str | None
    competitor_cited: list[dict]


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.post("/", response_model=ManualCitationOut, status_code=201)
async def submit_manual_citation(
    body: ManualCitationIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ManualCitationOut:
    await _set_ctx(session, tenant_id)

    # クエリと自社ドメイン、競合ドメインを取得
    query = (
        await session.scalars(
            select(TargetQuery).where(
                TargetQuery.tenant_id == tenant_id, TargetQuery.id == body.query_id
            )
        )
    ).one_or_none()
    if not query:
        raise HTTPException(status_code=404, detail="target query not found")

    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    competitors = list(
        (
            await session.scalars(
                select(Competitor).where(
                    Competitor.tenant_id == tenant_id, Competitor.is_active.is_(True)
                )
            )
        ).all()
    )
    profile = MatchProfile(
        self_domain=tenant.domain,
        self_aliases=[tenant.name],
        competitor_domains=[c.domain for c in competitors],
    )
    match = evaluate(body.response_text, body.cited_urls, profile)

    log_row = CitationLog(
        tenant_id=tenant_id,
        query_id=body.query_id,
        llm_provider=body.llm_provider,
        query_date=body.query_date or date.today(),
        response_text=body.response_text,
        cited_urls=body.cited_urls,
        self_cited=match.self_cited,
        competitor_cited=match.competitor_cited,
        raw_response={"source": "manual"},
    )
    session.add(log_row)
    await session.flush()
    result = ManualCitationOut(
        id=log_row.id,
        self_cited=match.self_cited,
        self_match_reason=match.self_match_reason,
        competitor_cited=match.competitor_cited,
    )
    await session.commit()
    return result
