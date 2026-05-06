"""システム状態 API(設定 → システム状態 タブ用)。

GET /system/jobs   ジョブ実行履歴(直近 N 時間)を返す
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.enums import JobStatusEnum
from app.db.models.job_execution_log import JobExecutionLog

router = APIRouter(prefix="/system", tags=["system"])


class JobLogOut(BaseModel):
    id: uuid.UUID
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: int | None
    error_text: str | None


@router.get("/jobs", response_model=list[JobLogOut])
async def list_jobs(
    hours: int = Query(72, ge=1, le=720, description="何時間前までのログを返すか"),
    limit: int = Query(200, ge=1, le=500),
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[JobLogOut]:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    stmt = (
        select(JobExecutionLog)
        .where(
            JobExecutionLog.tenant_id == tenant_id,
            JobExecutionLog.started_at >= cutoff,
        )
        .order_by(desc(JobExecutionLog.started_at))
        .limit(limit)
    )
    rows = list((await session.scalars(stmt)).all())
    out: list[JobLogOut] = []
    for r in rows:
        dur = (
            int((r.finished_at - r.started_at).total_seconds())
            if r.finished_at
            else None
        )
        out.append(
            JobLogOut(
                id=r.id,
                job_name=r.job_name,
                status=r.status.value if isinstance(r.status, JobStatusEnum) else str(r.status),
                started_at=r.started_at,
                finished_at=r.finished_at,
                duration_seconds=dur,
                error_text=r.error_text,
            )
        )
    return out
