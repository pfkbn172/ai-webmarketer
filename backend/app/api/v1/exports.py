"""CSV エクスポート(Phase 1: 同期ダウンロード)。"""

import csv
import io
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.citation_log import CitationLog
from app.db.models.content import Content
from app.db.models.inquiry import Inquiry
from app.db.models.kpi_log import KpiLog
from app.db.models.target_query import TargetQuery

router = APIRouter(prefix="/exports", tags=["exports"])

ALLOWED = {"kpi", "citation", "contents", "inquiries", "target_queries"}


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/{kind}.csv")
async def export_csv(
    kind: str,
    days: int = 30,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    if kind not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")
    await _set_ctx(session, tenant_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    end = date.today()
    start = end - timedelta(days=days)

    if kind == "kpi":
        writer.writerow(
            ["date", "sessions", "clicks", "impressions", "avg_position", "ai_citation_count", "inquiries_count"]
        )
        rows = list(
            (
                await session.scalars(
                    select(KpiLog)
                    .where(KpiLog.tenant_id == tenant_id, KpiLog.date.between(start, end))
                    .order_by(KpiLog.date)
                )
            ).all()
        )
        for r in rows:
            writer.writerow(
                [r.date, r.sessions, r.clicks, r.impressions, r.avg_position, r.ai_citation_count, r.inquiries_count]
            )
    elif kind == "citation":
        writer.writerow(["query_date", "llm_provider", "self_cited", "competitor_cited", "response_text"])
        rows = list(
            (
                await session.scalars(
                    select(CitationLog).where(
                        CitationLog.tenant_id == tenant_id,
                        CitationLog.query_date.between(start, end),
                    )
                )
            ).all()
        )
        for r in rows:
            writer.writerow(
                [
                    r.query_date,
                    r.llm_provider.value,
                    r.self_cited,
                    r.competitor_cited,
                    (r.response_text or "")[:500],
                ]
            )
    elif kind == "contents":
        writer.writerow(["title", "url", "status", "published_at", "schema_score"])
        rows = list((await session.scalars(select(Content).where(Content.tenant_id == tenant_id))).all())
        for r in rows:
            writer.writerow([r.title, r.url, r.status.value, r.published_at, r.schema_score])
    elif kind == "inquiries":
        writer.writerow(["received_at", "industry", "company_size", "source_channel", "ai_origin", "status"])
        rows = list((await session.scalars(select(Inquiry).where(Inquiry.tenant_id == tenant_id))).all())
        for r in rows:
            writer.writerow(
                [
                    r.received_at,
                    r.industry,
                    r.company_size,
                    r.source_channel.value,
                    r.ai_origin.value if r.ai_origin else "",
                    r.status.value,
                ]
            )
    elif kind == "target_queries":
        writer.writerow(["query_text", "cluster_id", "priority", "expected_conversion", "is_active"])
        rows = list(
            (await session.scalars(select(TargetQuery).where(TargetQuery.tenant_id == tenant_id))).all()
        )
        for r in rows:
            writer.writerow([r.query_text, r.cluster_id, r.priority, r.expected_conversion, r.is_active])

    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{kind}.csv"'}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)
