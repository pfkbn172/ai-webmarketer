"""WordPress REST API への書き戻し(JSON-LD 注入 / llms.txt の更新等)。

認証: Application Password(tenant_credentials.wordpress に user_login / app_password 保管)
"""

import json
import uuid

import httpx

from app.db.models.enums import CredentialProviderEnum
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.logger import get_logger
from app.utils.retry import retry_async

log = get_logger(__name__)


class WordPressClient:
    def __init__(
        self, base_url: str, user_login: str, app_password: str
    ) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (user_login, app_password)

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(httpx.HTTPError,))
    async def update_post_meta(self, post_id: int, meta: dict) -> dict:
        """投稿のカスタムフィールドを更新(JSON-LD 用 meta_key: 'jsonld')。"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/wp-json/wp/v2/posts/{post_id}",
                auth=self._auth,
                json={"meta": meta},
            )
            resp.raise_for_status()
            return resp.json()

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(httpx.HTTPError,))
    async def upload_jsonld(self, post_id: int, jsonld_blocks: list[dict]) -> None:
        """投稿の meta フィールド `marketer_jsonld` に JSON 配列で保管。
        WP テーマ側で <head> に <script type="application/ld+json"> を出力する想定。
        """
        await self.update_post_meta(
            post_id, {"marketer_jsonld": json.dumps(jsonld_blocks, ensure_ascii=False)}
        )

    @retry_async(max_attempts=3, base_delay=2.0, retriable_exceptions=(httpx.HTTPError,))
    async def upload_root_file(self, path: str, content: str) -> None:
        """サイトルート直下のファイル(llms.txt 等)を更新。

        WP REST API には標準のファイル設置 API が無いため、専用プラグイン or
        テーマ側のカスタムエンドポイント `/wp-json/marketer/v1/root-file` を想定。
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.put(
                f"{self._base}/wp-json/marketer/v1/root-file",
                auth=self._auth,
                json={"path": path, "content": content},
            )
            resp.raise_for_status()


async def get_wp_client(
    repo: TenantCredentialRepository, tenant_id: uuid.UUID
) -> WordPressClient | None:
    cred = await repo.get_decrypted(tenant_id, CredentialProviderEnum.wordpress)
    if not cred:
        return None
    base_url = cred.get("base_url")
    user = cred.get("user_login")
    app_password = cred.get("app_password")
    if not (base_url and user and app_password):
        return None
    return WordPressClient(base_url, user, app_password)
