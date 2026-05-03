"""tenants.business_context の取得・更新 + AI ヒアリングによる初期生成 API。

Phase 2 戦略思考レイヤーの中核データ。LLM プロンプトに毎回注入される。
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.factory import AIProviderFactory
from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.enums import AIUseCaseEnum
from app.db.models.tenant import Tenant
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/business-context", tags=["business_context"])


class BusinessContext(BaseModel):
    """JSONB の中身を Pydantic でゆるく型付け。未指定キーは無視。"""

    stage: str | None = None  # solo / micro / smb / enterprise
    geographic_base: list[str] = []
    geographic_expansion: list[str] = []
    unique_value: list[str] = []
    primary_offerings: list[str] = []
    target_customer: str | None = None
    weak_segments: list[str] = []
    strong_segments: list[str] = []
    compliance_constraints: list[str] = []


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/", response_model=BusinessContext)
async def get_business_context(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> BusinessContext:
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    return BusinessContext(**(tenant.business_context or {}))


@router.put("/", response_model=BusinessContext)
async def update_business_context(
    body: BusinessContext,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> BusinessContext:
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    tenant.business_context = body.model_dump()
    await session.commit()
    return body


class HearingRequest(BaseModel):
    """AI ヒアリング: 既存の business_context + 自由記述メモから JSON を構造化生成。"""

    free_text: str  # キセが書く事業の自己紹介自由記述


@router.post("/ai-hearing", response_model=BusinessContext)
async def ai_hearing(
    body: HearingRequest,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> BusinessContext:
    """自由記述から business_context JSON を AI に組み立てさせる。"""
    await _set_ctx(session, tenant_id)
    tenant = (
        await session.scalars(select(Tenant).where(Tenant.id == tenant_id))
    ).one()
    existing = tenant.business_context or {}

    prompt = (
        f"以下の事業者の自己紹介から、戦略 LLM プロンプトに渡す business_context JSON を"
        f"組み立ててください。既存値とマージしてください(空欄は既存値を保持)。\n\n"
        f"テナント名: {tenant.name}\n"
        f"業種: {tenant.industry or '不明'}\n"
        f"ドメイン: {tenant.domain}\n"
        f"既存 business_context: {json.dumps(existing, ensure_ascii=False)}\n\n"
        f"自己紹介:\n{body.free_text}\n\n"
        f"出力フォーマット(JSON、追加コメント不要):\n"
        f"{{\n"
        f'  "stage": "solo|micro|smb|enterprise",\n'
        f'  "geographic_base": ["..."],\n'
        f'  "geographic_expansion": ["..."],\n'
        f'  "unique_value": ["..."],\n'
        f'  "primary_offerings": ["..."],\n'
        f'  "target_customer": "...",\n'
        f'  "weak_segments": ["..."],\n'
        f'  "strong_segments": ["..."],\n'
        f'  "compliance_constraints": ["..."]\n'
        f"}}"
    )

    try:
        provider = await AIProviderFactory.get_for_use_case(
            session, tenant_id, AIUseCaseEnum.eeat_analysis
        )
        res = await provider.generate(
            system_prompt="あなたは事業ヒアリングの専門家です。",
            user_prompt=prompt,
            response_format="json",
            max_tokens=2000,
            temperature=0.3,
        )
        parsed = json.loads(res.text)
    except Exception as exc:
        log.warning("ai_hearing_failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"AI ヒアリング失敗: {type(exc).__name__}"
        ) from None

    merged = {**existing, **{k: v for k, v in parsed.items() if v}}
    tenant.business_context = merged
    await session.commit()
    return BusinessContext(**merged)
