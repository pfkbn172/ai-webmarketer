"""Google OAuth 認可フロー(GSC / GA4 共通)を CLI で実行し、refresh_token を取得して
tenant_credentials に Fernet 暗号化保存する。

使い方:
    cd backend
    # GSC: site_url を必ず指定する
    .venv/bin/python -m scripts.google_oauth_setup \
        --tenant-id <uuid> \
        --provider gsc \
        --client-secret-json /path/to/client_secret.json \
        --scopes https://www.googleapis.com/auth/webmasters.readonly \
        --site-url sc-domain:kiseeeen.co.jp

    # GA4: property_id を必ず指定する
    .venv/bin/python -m scripts.google_oauth_setup \
        --tenant-id <uuid> \
        --provider ga4 \
        --client-secret-json /path/to/client_secret.json \
        --scopes https://www.googleapis.com/auth/analytics.readonly \
        --property-id 123456789

GCP コンソールで作成した OAuth 2.0 Client ID(Desktop タイプ)の JSON ファイルを渡す。
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
        help="OAuth コールバック用 localhost ポート",
    )
    parser.add_argument(
        "--site-url",
        help="GSC のサイト URL(例: sc-domain:kiseeeen.co.jp)。provider=gsc で必須",
    )
    parser.add_argument(
        "--property-id",
        help="GA4 のプロパティ ID(例: 123456789)。provider=ga4 で必須",
    )
    args = parser.parse_args()

    if args.provider == "gsc" and not args.site_url:
        print("[ERROR] --site-url を指定してください(gsc は必須)", file=sys.stderr)
        return 2
    if args.provider == "ga4" and not args.property_id:
        print("[ERROR] --property-id を指定してください(ga4 は必須)", file=sys.stderr)
        return 2

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

    client_data = json.loads(args.client_secret_json.read_text())["installed"]
    payload: dict = {
        "client_id": client_data["client_id"],
        "client_secret": client_data["client_secret"],
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "scopes": list(args.scopes),
    }
    if args.site_url:
        payload["site_url"] = args.site_url
    if args.property_id:
        payload["property_id"] = args.property_id

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
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

    print(
        f"[INFO] tenant={args.tenant_id} provider={args.provider} の認証情報を保管しました"
    )
    if args.site_url:
        print(f"[INFO] site_url={args.site_url}")
    if args.property_id:
        print(f"[INFO] property_id={args.property_id}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
