"""GA4 過去データを遡って取得し DB に upsert する。

通常の週次ジョブは days=7 だけだが、起動初期に管理画面側にある過去データを
DB に流し込むためのワンショット。冪等(既存日次は UPSERT)。

使い方:
    cd backend
    .venv/bin/python -m scripts.backfill_ga4 --tenant-id <UUID> --days 540

GA4 Data API は API 呼び出し回数のクォータがあるので、--chunk-days で分割
取得する(既定 30 日)。chunk_days を小さくすると安全だが時間が増える。
"""

import argparse
import asyncio
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.collectors.ga4.client import Ga4Client
from app.collectors.google_oauth import load_google_credentials
from app.db.models.enums import CredentialProviderEnum
from app.db.models.ga4_ai_referral_daily import Ga4AiReferralDaily
from app.db.models.ga4_daily_metric import Ga4DailyMetric
from app.db.models.ga4_page_daily import Ga4PageDaily
from app.db.models.tenant_credential import TenantCredential
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.settings import settings
from app.utils.encryption import decrypt_json


async def _set_ctx(session, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


_BATCH = 1000  # asyncpg は 1 文中の bind 引数を 32767 に制限


async def _upsert_daily(session, tenant_id, rows):
    if not rows:
        return
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "sessions": r.sessions,
            "users": r.users,
            "bounce_rate": r.bounce_rate,
            "conversions": r.conversions,
            "organic_sessions": r.organic_sessions,
        }
        for r in rows
    ]
    for i in range(0, len(payload), _BATCH):
        chunk = payload[i : i + _BATCH]
        stmt = pg_insert(Ga4DailyMetric).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_daily_tenant_date",
            set_={
                "sessions": stmt.excluded.sessions,
                "users": stmt.excluded.users,
                "bounce_rate": stmt.excluded.bounce_rate,
                "conversions": stmt.excluded.conversions,
                "organic_sessions": stmt.excluded.organic_sessions,
            },
        )
        await session.execute(stmt)


async def _upsert_pages(session, tenant_id, rows):
    if not rows:
        return
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "page_path": r.page_path,
            "sessions": r.sessions,
            "users": r.users,
            "conversions": r.conversions,
        }
        for r in rows
    ]
    for i in range(0, len(payload), _BATCH):
        chunk = payload[i : i + _BATCH]
        stmt = pg_insert(Ga4PageDaily).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_pd_tenant_date_path",
            set_={
                "sessions": stmt.excluded.sessions,
                "users": stmt.excluded.users,
                "conversions": stmt.excluded.conversions,
            },
        )
        await session.execute(stmt)


async def _upsert_ai_refs(session, tenant_id, rows):
    if not rows:
        return
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "source_host": r.source_host,
            "sessions": r.sessions,
        }
        for r in rows
    ]
    for i in range(0, len(payload), _BATCH):
        chunk = payload[i : i + _BATCH]
        stmt = pg_insert(Ga4AiReferralDaily).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_ai_ref_tenant_date_host",
            set_={"sessions": stmt.excluded.sessions},
        )
        await session.execute(stmt)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--days", type=int, default=540, help="今日から何日遡るか")
    parser.add_argument(
        "--chunk-days", type=int, default=30, help="API 呼び出しの分割サイズ"
    )
    args = parser.parse_args()

    tenant_id = uuid.UUID(args.tenant_id)
    end = date.today() - timedelta(days=1)
    overall_start = end - timedelta(days=args.days - 1)

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    total_daily = 0
    total_page = 0
    total_ai = 0

    async with factory() as session:
        await _set_ctx(session, tenant_id)
        # 認証情報 + property_id 取得
        repo = TenantCredentialRepository(session)
        creds = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.ga4)
        cred = (
            await session.scalars(
                select(TenantCredential).where(
                    TenantCredential.tenant_id == tenant_id,
                    TenantCredential.provider == CredentialProviderEnum.ga4,
                )
            )
        ).one_or_none()
        if cred is None:
            print("[error] GA4 credential が見つかりません", file=sys.stderr)
            return 1
        payload = decrypt_json(cred.encrypted_data)
        property_id = payload.get("property_id")
        if not property_id:
            print("[error] property_id が登録されていません", file=sys.stderr)
            return 1
        client = Ga4Client(creds, property_id=property_id)

        cursor = end
        while cursor >= overall_start:
            chunk_end = cursor
            chunk_start = max(overall_start, chunk_end - timedelta(days=args.chunk_days - 1))
            print(f"[ga4] {chunk_start} - {chunk_end} を取得中…", flush=True)
            try:
                daily = await client.daily_metrics(chunk_start, chunk_end)
                pages = await client.page_metrics(chunk_start, chunk_end)
                ai_refs = await client.ai_referrals(chunk_start, chunk_end)
            except Exception as e:
                print(f"[ga4] 取得失敗 ({chunk_start}-{chunk_end}): {e}", file=sys.stderr)
                break
            await _upsert_daily(session, tenant_id, daily)
            await _upsert_pages(session, tenant_id, pages)
            await _upsert_ai_refs(session, tenant_id, ai_refs)
            await session.commit()
            await _set_ctx(session, tenant_id)  # commit で context が消える可能性に備え
            total_daily += len(daily)
            total_page += len(pages)
            total_ai += len(ai_refs)
            cursor = chunk_start - timedelta(days=1)

    await engine.dispose()
    print(
        f"[ga4] 完了: daily={total_daily}, page={total_page}, ai_referral={total_ai}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
