"""tenant_credentials の読み書き。

API 認証情報は Fernet 暗号化済み JSON として encrypted_data に保管される。
読み出すと dict で返り、書き込み時は dict を渡せば暗号化される。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.utils.encryption import decrypt_json, encrypt_json


class TenantCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_decrypted(
        self, tenant_id: uuid.UUID, provider: CredentialProviderEnum
    ) -> dict | None:
        stmt = select(TenantCredential).where(
            TenantCredential.tenant_id == tenant_id,
            TenantCredential.provider == provider,
        )
        row = (await self.session.scalars(stmt)).one_or_none()
        if row is None:
            return None
        return decrypt_json(row.encrypted_data)

    async def upsert(
        self,
        tenant_id: uuid.UUID,
        provider: CredentialProviderEnum,
        payload: dict,
    ) -> TenantCredential:
        encrypted = encrypt_json(payload)
        stmt = select(TenantCredential).where(
            TenantCredential.tenant_id == tenant_id,
            TenantCredential.provider == provider,
        )
        row = (await self.session.scalars(stmt)).one_or_none()
        if row is None:
            row = TenantCredential(
                tenant_id=tenant_id,
                provider=provider,
                encrypted_data=encrypted,
            )
            self.session.add(row)
        else:
            row.encrypted_data = encrypted
        await self.session.flush()
        return row
