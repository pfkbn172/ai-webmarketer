"""月次/週次レポート API。

- /api/v1/reports                   : 一覧
- /api/v1/reports/{id}              : 詳細
- /api/v1/reports/{id}/share        : share_token を発行(POST) / 取り消し(DELETE)
- /api/v1/reports/{id}/pdf          : ログイン後の PDF ダウンロード
- /api/v1/public/reports/{token}    : 公開トークン経由(認証不要)
- /api/v1/public/reports/{token}/pdf: 公開トークン経由 PDF
"""

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.report import Report
from app.services.report_pdf import render_report_to_pdf

router = APIRouter(prefix="/reports", tags=["reports"])
public_router = APIRouter(prefix="/public/reports", tags=["public-reports"])


class ReportSummary(BaseModel):
    id: uuid.UUID
    period: str
    report_type: str
    generated_at: datetime
    has_summary: bool
    share_token: str | None


class ReportDetail(BaseModel):
    id: uuid.UUID
    period: str
    report_type: str
    generated_at: datetime
    summary_html: str | None
    action_plan: dict | None
    share_token: str | None


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("", response_model=list[ReportSummary])
async def list_reports(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ReportSummary]:
    await _set_ctx(session, tenant_id)
    rows = list(
        (
            await session.scalars(
                select(Report)
                .where(Report.tenant_id == tenant_id)
                .order_by(Report.generated_at.desc())
            )
        ).all()
    )
    return [
        ReportSummary(
            id=r.id,
            period=r.period,
            report_type=r.report_type,
            generated_at=r.generated_at,
            has_summary=bool(r.summary_html),
            share_token=r.share_token,
        )
        for r in rows
    ]


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ReportDetail:
    await _set_ctx(session, tenant_id)
    r = (
        await session.scalars(
            select(Report).where(
                Report.id == report_id, Report.tenant_id == tenant_id
            )
        )
    ).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    return ReportDetail(
        id=r.id,
        period=r.period,
        report_type=r.report_type,
        generated_at=r.generated_at,
        summary_html=r.summary_html,
        action_plan=r.action_plan,
        share_token=r.share_token,
    )


class ShareTokenOut(BaseModel):
    share_token: str
    public_url_path: str


@router.post("/{report_id}/share", response_model=ShareTokenOut)
async def create_share_token(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> ShareTokenOut:
    await _set_ctx(session, tenant_id)
    r = (
        await session.scalars(
            select(Report).where(
                Report.id == report_id, Report.tenant_id == tenant_id
            )
        )
    ).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    r.share_token = secrets.token_urlsafe(32)
    await session.commit()
    return ShareTokenOut(
        share_token=r.share_token, public_url_path=f"/api/v1/public/reports/{r.share_token}"
    )


@router.delete("/{report_id}/share", status_code=204)
async def revoke_share_token(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _set_ctx(session, tenant_id)
    r = (
        await session.scalars(
            select(Report).where(
                Report.id == report_id, Report.tenant_id == tenant_id
            )
        )
    ).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    r.share_token = None
    await session.commit()
    return Response(status_code=204)


@router.get("/{report_id}/pdf")
async def download_pdf(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _set_ctx(session, tenant_id)
    r = (
        await session.scalars(
            select(Report).where(
                Report.id == report_id, Report.tenant_id == tenant_id
            )
        )
    ).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    return _build_pdf_response(r)


# ---- public (auth 不要) ----


@public_router.get("/{token}", response_model=ReportDetail)
async def get_public_report(
    token: str, session: AsyncSession = Depends(get_db_session)
) -> ReportDetail:
    # RLS バイパス: 共有トークン経由は tenant_id 制約を効かせるために app.tenant_id を
    # 当該レコードの tenant_id にセットする(まず非 RLS で取得→セット→詳細を返す)。
    # 実装簡略化のためトークンユニーク性に依存して直接取得する。
    r = (
        await session.scalars(select(Report).where(Report.share_token == token))
    ).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found or not shared")
    return ReportDetail(
        id=r.id,
        period=r.period,
        report_type=r.report_type,
        generated_at=r.generated_at,
        summary_html=r.summary_html,
        action_plan=r.action_plan,
        share_token=r.share_token,
    )


@public_router.get("/{token}/pdf")
async def get_public_report_pdf(
    token: str, session: AsyncSession = Depends(get_db_session)
) -> Response:
    r = (
        await session.scalars(select(Report).where(Report.share_token == token))
    ).one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="report not found or not shared")
    return _build_pdf_response(r)


def _build_pdf_response(r: Report) -> Response:
    title = f"{'月次' if r.report_type == 'monthly' else '週次'}レポート {r.period}"
    pdf = render_report_to_pdf(period=r.period, title=title, summary_html=r.summary_html)
    headers = {
        "Content-Disposition": f'attachment; filename="report-{r.period}.pdf"',
    }
    return Response(content=pdf, media_type="application/pdf", headers=headers)
