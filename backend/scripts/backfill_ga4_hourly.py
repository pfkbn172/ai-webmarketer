"""GA4 hourly メトリクスを過去全期間バックフィル。

実行例:
  cd /var/www/ai-web-marketer/backend
  .venv/bin/python -m scripts.backfill_ga4_hourly \\
      --tenant-id 7c59f23a-a94d-4a13-9910-a309d7743c22 \\
      --start 2024-11-11

  # 期間省略時は ga4_daily_metrics の min(date) を起点、終点は昨日
  .venv/bin/python -m scripts.backfill_ga4_hourly --tenant-id <TID>

GA4 Data API は dateHour ディメンションで「日付 × 時間帯」のセッションを返す。
1 リクエストあたりの行数上限(2.5 万行 / 1 リクエスト時点 v1beta)に余裕を持たせるため、
30 日ごとに分割して取得する(30日 × 24h = 720行 で安全圏)。
"""

import argparse
import asyncio
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import text

from app.collectors.ga4.client import Ga4Client
from app.collectors.ga4.runner import _upsert_hourly_rows
from app.collectors.google_oauth import load_google_credentials
from app.db.base import SessionLocal
from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.encryption import decrypt_json
from app.utils.logger import get_logger
from sqlalchemy import select

log = get_logger(__name__)


CHUNK_DAYS = 30


async def _resolve_window(
    session, tenant_id: uuid.UUID, start: date | None, end: date | None
) -> tuple[date, date]:
    if end is None:
        end = date.today() - timedelta(days=1)
    if start is None:
        # ga4_daily_metrics の min(date) を起点に揃える
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


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--start", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("--end", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    args = parser.parse_args()
    tenant_id = uuid.UUID(args.tenant_id)

    async with SessionLocal() as session:
        # property_id を取り出す
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
            raise SystemExit("property_id missing in credential payload")

        repo = TenantCredentialRepository(session)
        oauth = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.ga4)
        client = Ga4Client(oauth, property_id=property_id)

        start, end = await _resolve_window(session, tenant_id, args.start, args.end)
        total = 0
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), end)
            log.info(
                "ga4_hourly_backfill_chunk",
                tenant_id=str(tenant_id),
                start=chunk_start.isoformat(),
                end=chunk_end.isoformat(),
            )
            rows = await client.hourly_metrics(chunk_start, chunk_end)
            if rows:
                await _upsert_hourly_rows(session, tenant_id, rows)
                await session.commit()
            total += len(rows)
            print(
                f"  {chunk_start} 〜 {chunk_end}: {len(rows):>5} rows (cumulative {total})"
            )
            chunk_start = chunk_end + timedelta(days=1)
        print(f"DONE. total upserted rows = {total}")


if __name__ == "__main__":
    asyncio.run(main())
