"""引用ログ取得 API。クエリ別の直近 4 週分カウント等を返す。"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.citation_log import CitationLog
from app.db.models.target_query import TargetQuery

router = APIRouter(prefix="/citation-logs", tags=["citation_logs"])


class CitationCellOut(BaseModel):
    llm: str
    self_cited: int
    total: int


class CitationRowOut(BaseModel):
    query_id: uuid.UUID
    query_text: str
    cells: list[CitationCellOut]


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/summary", response_model=list[CitationRowOut])
async def summary(
    days: int = 28,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CitationRowOut]:
    await _set_ctx(session, tenant_id)
    end = date.today()
    start = end - timedelta(days=days)
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

    # query_id → llm → (self_count, total)
    by_q: dict[uuid.UUID, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for log_ in logs:
        cell = by_q[log_.query_id][log_.llm_provider.value]
        cell[1] += 1
        if log_.self_cited:
            cell[0] += 1

    out: list[CitationRowOut] = []
    for q in queries:
        cells = [
            CitationCellOut(llm=llm, self_cited=v[0], total=v[1])
            for llm, v in by_q.get(q.id, {}).items()
        ]
        out.append(CitationRowOut(query_id=q.id, query_text=q.query_text, cells=cells))
    return out
