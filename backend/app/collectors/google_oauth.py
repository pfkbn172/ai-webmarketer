"""Google OAuth 共通: tenant_credentials から refresh_token を取り出して Credentials を構築。

本モジュールは GSC / GA4 の両方から呼ばれる。
保管 JSON のスキーマ:
    {
        "client_id": "...",
        "client_secret": "...",
        "refresh_token": "...",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["..."]
    }
"""

import uuid
from dataclasses import dataclass

from google.oauth2.credentials import Credentials

from app.db.models.enums import CredentialProviderEnum
from app.db.repositories.tenant_credential import TenantCredentialRepository


class CredentialsNotFoundError(Exception):
    """tenant_credentials に該当 provider の認証情報が登録されていない。"""


@dataclass(frozen=True, slots=True)
class GoogleOAuthCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    token_uri: str
    scopes: list[str]

    def to_google_credentials(self) -> Credentials:
        return Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri=self.token_uri,
            scopes=self.scopes,
        )


async def load_google_credentials(
    repo: TenantCredentialRepository,
    tenant_id: uuid.UUID,
    provider: CredentialProviderEnum,
) -> GoogleOAuthCredentials:
    payload = await repo.get_decrypted(tenant_id, provider)
    if payload is None:
        raise CredentialsNotFoundError(
            f"tenant_credentials に {provider.value} の認証情報が登録されていません"
        )
    try:
        return GoogleOAuthCredentials(
            client_id=payload["client_id"],
            client_secret=payload["client_secret"],
            refresh_token=payload["refresh_token"],
            token_uri=payload.get("token_uri", "https://oauth2.googleapis.com/token"),
            scopes=payload.get("scopes", []),
        )
    except KeyError as exc:
        raise CredentialsNotFoundError(
            f"認証情報 JSON に必須キー {exc} が含まれていません"
        ) from None
