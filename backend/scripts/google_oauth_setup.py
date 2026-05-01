"""Google OAuth 認可フロー(GSC / GA4 共通)を CLI で実行し、refresh_token を取得して
tenant_credentials に Fernet 暗号化保存する。

使い方:
    cd backend
    .venv/bin/python -m scripts.google_oauth_setup \
        --tenant-id <uuid> \
        --provider gsc \
        --client-secret-json /path/to/client_secret.json \
        --scopes https://www.googleapis.com/auth/webmasters.readonly

    # GA4 の場合
    .venv/bin/python -m scripts.google_oauth_setup \
        --tenant-id <uuid> \
        --provider ga4 \
        --client-secret-json /path/to/client_secret.json \
        --scopes https://www.googleapis.com/auth/analytics.readonly

GCP コンソールで作成した OAuth 2.0 Client ID(Desktop タイプ)の JSON ファイルを渡す。
ブラウザが自動起動して同意画面が出る → 認可後、refresh_token を取得して DB に保管。
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.enums import CredentialProviderEnum
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.settings import settings


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--provider",
        required=True,
        choices=[p.value for p in CredentialProviderEnum],
    )
    parser.add_argument("--client-secret-json", required=True, type=Path)
    parser.add_argument(
        "--scopes",
        required=True,
        nargs="+",
        help="複数スペース区切り(例: https://www.googleapis.com/auth/webmasters.readonly)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="OAuth コールバック用 localhost ポート(GCP の redirect URI と一致させる)",
    )
    args = parser.parse_args()

    if not args.client_secret_json.exists():
        print(f"[ERROR] {args.client_secret_json} が見つかりません", file=sys.stderr)
        return 2

    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_secret_json), scopes=args.scopes
    )
    creds = flow.run_local_server(port=args.port, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        print(
            "[ERROR] refresh_token が取得できませんでした。"
            "GCP の OAuth クライアントを作り直すか、prompt='consent' で再実行してください。",
            file=sys.stderr,
        )
        return 3

    payload = {
        "client_id": json.loads(args.client_secret_json.read_text())["installed"]["client_id"],
        "client_secret": json.loads(args.client_secret_json.read_text())["installed"]["client_secret"],
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "scopes": list(args.scopes),
    }

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # RLS 回避: テナント自身を参照する書き込みのため、SET app.tenant_id を発行
        from sqlalchemy import text
        tenant_uuid = uuid.UUID(args.tenant_id)
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_uuid)},
        )
        repo = TenantCredentialRepository(session)
        await repo.upsert(
            tenant_uuid,
            CredentialProviderEnum(args.provider),
            payload,
        )
        await session.commit()
    await engine.dispose()

    print(f"[INFO] tenant={args.tenant_id} provider={args.provider} の認証情報を保管しました")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
