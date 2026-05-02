"""tenant_credentials の管理 API。

設計指針 10.1:
- API キーは Fernet で暗号化保管、レスポンスでは平文を返さない
- マスク表示(先頭 4 文字 + ... + 末尾 4 文字)で「登録済か」がわかれば十分
- 削除と上書き(再登録)は許可、平文取得 API は提供しない
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.base import get_db_session
from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.db.repositories.tenant_credential import TenantCredentialRepository

router = APIRouter(prefix="/credentials", tags=["credentials"])


class CredentialStatus(BaseModel):
    provider: str
    registered: bool
    masked: str | None  # 'sk-p...xxxx' 形式
    updated_at: str | None
    fields: list[str] = []  # 登録されているキー名(api_key, base_url, refresh_token 等)


# UI で扱う provider 一覧(設定画面でカード表示)
PROVIDERS_FOR_UI: list[CredentialProviderEnum] = [
    CredentialProviderEnum.gsc,
    CredentialProviderEnum.ga4,
    CredentialProviderEnum.gemini_ai_engine,
    CredentialProviderEnum.gemini_citation_monitor,
    CredentialProviderEnum.openai,
    CredentialProviderEnum.anthropic,
    CredentialProviderEnum.perplexity,
    CredentialProviderEnum.serpapi,
    CredentialProviderEnum.wordpress,
    CredentialProviderEnum.resend,
]


def _mask_value(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@router.get("/", response_model=list[CredentialStatus])
async def list_credentials(
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[CredentialStatus]:
    await _set_ctx(session, tenant_id)
    repo = TenantCredentialRepository(session)
    out: list[CredentialStatus] = []
    for prov in PROVIDERS_FOR_UI:
        # 行が存在するかを別途確認(get_decrypted は中身を返すだけ)
        row = (
            await session.scalars(
                select(TenantCredential).where(
                    TenantCredential.tenant_id == tenant_id,
                    TenantCredential.provider == prov,
                )
            )
        ).one_or_none()
        if not row:
            out.append(
                CredentialStatus(
                    provider=prov.value, registered=False, masked=None, updated_at=None
                )
            )
            continue
        payload = await repo.get_decrypted(tenant_id, prov)
        api_key_or_token = (
            (payload or {}).get("api_key")
            or (payload or {}).get("refresh_token")
            or (payload or {}).get("app_password")
        )
        out.append(
            CredentialStatus(
                provider=prov.value,
                registered=True,
                masked=_mask_value(api_key_or_token),
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
                fields=list((payload or {}).keys()),
            )
        )
    return out


class CredentialUpsertIn(BaseModel):
    """provider に応じて使うフィールドが違う。

    - api_key 系(openai/anthropic/perplexity/serpapi/gemini_*/resend): api_key
    - wordpress: base_url, user_login, app_password
    - gsc/ga4: refresh_token は OAuth フロー専用、ここからは編集不可。
              ただし site_url / property_id だけ後から差し替えたい用途は許容
    """

    api_key: str | None = None
    base_url: str | None = None
    user_login: str | None = None
    app_password: str | None = None
    site_url: str | None = None
    property_id: str | None = None


@router.put("/{provider}", response_model=CredentialStatus)
async def upsert_credential(
    provider: str,
    body: CredentialUpsertIn,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> CredentialStatus:
    try:
        prov = CredentialProviderEnum(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail="unknown provider") from None

    # OAuth が必要な provider(gsc/ga4)は本 API では認証編集不可
    # (scripts/google_oauth_setup.py 経由)。ただし site_url / property_id だけは
    # 後から更新可能としている。
    if prov in (CredentialProviderEnum.gsc, CredentialProviderEnum.ga4) and not (
        body.site_url or body.property_id
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{provider} の認証は scripts/google_oauth_setup.py で行ってください。"
                "本 API では site_url / property_id の差し替えのみ可能です。"
            ),
        )

    await _set_ctx(session, tenant_id)
    repo = TenantCredentialRepository(session)

    # 既存値があれば取り出し、差分マージ(空欄フィールドは触らない)
    existing = await repo.get_decrypted(tenant_id, prov) or {}
    merged = dict(existing)
    for field in ("api_key", "base_url", "user_login", "app_password", "site_url", "property_id"):
        v = getattr(body, field)
        if v is not None and v != "":
            merged[field] = v

    if not merged:
        raise HTTPException(status_code=400, detail="登録する値が指定されていません")

    await repo.upsert(tenant_id, prov, merged)
    await session.commit()

    # 戻り値: マスク状態
    fresh = await repo.get_decrypted(tenant_id, prov) or {}
    masked = _mask_value(
        fresh.get("api_key") or fresh.get("refresh_token") or fresh.get("app_password")
    )
    return CredentialStatus(
        provider=prov.value,
        registered=True,
        masked=masked,
        updated_at=None,
        fields=list(fresh.keys()),
    )


@router.delete("/{provider}", status_code=204)
async def delete_credential(
    provider: str,
    tenant_id: uuid.UUID = Depends(require_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        prov = CredentialProviderEnum(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail="unknown provider") from None
    await _set_ctx(session, tenant_id)
    row = (
        await session.scalars(
            select(TenantCredential).where(
                TenantCredential.tenant_id == tenant_id,
                TenantCredential.provider == prov,
            )
        )
    ).one_or_none()
    if row:
        await session.delete(row)
        await session.commit()
