from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe。プロセスが応答するかだけを確認。"""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Readiness probe。DB に到達できるかも確認する。"""
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
