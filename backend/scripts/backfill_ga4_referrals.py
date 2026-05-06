"""GA4 リファラ(日次・時間別)を過去全期間バックフィル。

実行例:
  cd /var/www/ai-web-marketer/backend
  .venv/bin/python -m scripts.backfill_ga4_referrals \\
      --tenant-id 7c59f23a-a94d-4a13-9910-a309d7743c22

  # 期間省略時は ga4_daily_metrics の min(date) 起点、終点は昨日。
  # 時間別は cardinality が大きいので 7 日チャンク、日次は 30 日チャンク。
"""

import argparse
import asyncio
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, text

from app.collectors.ga4.client import Ga4Client
from app.collectors.ga4.runner import (
    _upsert_referral_daily,
    _upsert_referral_hourly,
)
from app.collectors.google_oauth import load_google_credentials
from app.db.base import SessionLocal
from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.encryption import decrypt_json
from app.utils.logger import get_logger

log = get_logger(__name__)


DAILY_CHUNK_DAYS = 30
HOURLY_CHUNK_DAYS = 7  # 時間別は cardinality が大きいので短く


async def _resolve_window(
    session, tenant_id: uuid.UUID, start: date | None, end: date | None
) -> tuple[date, date]:
    if end is None:
        end = date.today() - timedelta(days=1)
    if start is None:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        row = (
            await session.execute(
                text(
                    "SELECT MIN(date) FROM ga4_daily_metrics WHERE tenant_id = :tid"
                ),
                {"tid": str(tenant_id)},
            )
        ).first()
        if row is None or row[0] is None:
            raise SystemExit(
                "ga4_daily_metrics が空です。--start を明示してください。"
            )
        start = row[0]
    if start > end:
        raise SystemExit(f"start({start}) > end({end}) です。")
    return start, end


async def _backfill_daily(client: Ga4Client, session, tenant_id, start, end) -> int:
    total = 0
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=DAILY_CHUNK_DAYS - 1), end)
        rows = await client.referrals_daily(cur, chunk_end)
        if rows:
            await _upsert_referral_daily(session, tenant_id, rows)
            await session.commit()
        total += len(rows)
        print(f"  daily   {cur} 〜 {chunk_end}: {len(rows):>5} rows (cum {total})")
        cur = chunk_end + timedelta(days=1)
    return total


async def _backfill_hourly(client: Ga4Client, session, tenant_id, start, end) -> int:
    total = 0
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=HOURLY_CHUNK_DAYS - 1), end)
        rows = await client.referrals_hourly(cur, chunk_end)
        if rows:
            await _upsert_referral_hourly(session, tenant_id, rows)
            await session.commit()
        total += len(rows)
        print(f"  hourly  {cur} 〜 {chunk_end}: {len(rows):>5} rows (cum {total})")
        cur = chunk_end + timedelta(days=1)
    return total


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--start", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("--end", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("--skip-daily", action="store_true")
    parser.add_argument("--skip-hourly", action="store_true")
    args = parser.parse_args()
    tenant_id = uuid.UUID(args.tenant_id)

    async with SessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        cred = (
            await session.scalars(
                select(TenantCredential).where(
                    TenantCredential.tenant_id == tenant_id,
                    TenantCredential.provider == CredentialProviderEnum.ga4,
                )
            )
        ).one_or_none()
        if cred is None:
            raise SystemExit(f"GA4 credential not found for tenant {tenant_id}")
        payload = decrypt_json(cred.encrypted_data)
        property_id = payload.get("property_id")
        if not property_id:
            raise SystemExit("property_id missing")

        repo = TenantCredentialRepository(session)
        oauth = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.ga4)
        client = Ga4Client(oauth, property_id=property_id)

        start, end = await _resolve_window(session, tenant_id, args.start, args.end)
        print(f"window: {start} 〜 {end}")

        if not args.skip_daily:
            print("--- daily referrals ---")
            n = await _backfill_daily(client, session, tenant_id, start, end)
            print(f"daily total: {n}")
        if not args.skip_hourly:
            print("--- hourly referrals ---")
            n = await _backfill_hourly(client, session, tenant_id, start, end)
            print(f"hourly total: {n}")


if __name__ == "__main__":
    asyncio.run(main())
