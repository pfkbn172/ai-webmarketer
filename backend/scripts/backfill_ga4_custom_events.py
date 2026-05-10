"""GA4 カスタムイベント(2026-05 追加分)10 種をバックフィル。

対象テーブル:
  - ga4_ai_referral_event_daily / ga4_ai_crawler_daily / ga4_ai_crawler_page_daily
  - ga4_llms_txt_fetch_daily / ga4_article_read_complete_daily
  - ga4_text_copy_daily / ga4_outbound_click_daily / ga4_cta_click_daily
  - ga4_tool_use_daily / ga4_engagement_signal_daily

実行例:
  cd /var/www/ai-web-marketer/backend
  .venv/bin/python -m scripts.backfill_ga4_custom_events \\
      --tenant-id 7c59f23a-a94d-4a13-9910-a309d7743c22

  # デフォルト窓: 2026-05-10(イベント計測開始日) 〜 yesterday
  # 30 日チャンク、メソッド間 1 秒スリープ(GA4 Data API quota 50req/min/property 対策)
  # --only <key> で 1 メソッドだけ実行できる(例: --only ai_crawler)
"""

import argparse
import asyncio
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, text

from app.collectors.ga4.client import Ga4Client
from app.collectors.ga4.runner import (
    _upsert_ai_crawler,
    _upsert_ai_crawler_page,
    _upsert_ai_referral_events,
    _upsert_article_read,
    _upsert_cta_click,
    _upsert_engagement_signal,
    _upsert_llms_txt_fetch,
    _upsert_outbound_click,
    _upsert_text_copy,
    _upsert_tool_use,
)
from app.collectors.google_oauth import load_google_credentials
from app.db.base import SessionLocal
from app.db.models.enums import CredentialProviderEnum
from app.db.models.tenant_credential import TenantCredential
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.utils.encryption import decrypt_json
from app.utils.logger import get_logger

log = get_logger(__name__)


# 計測開始日(本体側で新規イベント追加した日)
EVENT_LAUNCH_DATE = date(2026, 5, 10)
CHUNK_DAYS = 30
SLEEP_BETWEEN_METHODS_SEC = 1.0


# (key, fetcher_attr, upserter)
COLLECTORS = (
    ("ai_referral_event", "ai_referral_events", _upsert_ai_referral_events),
    ("ai_crawler", "ai_crawler_visits", _upsert_ai_crawler),
    ("ai_crawler_page", "ai_crawler_pages", _upsert_ai_crawler_page),
    ("llms_txt_fetch", "llms_txt_fetches", _upsert_llms_txt_fetch),
    ("article_read", "article_read_completes", _upsert_article_read),
    ("text_copy", "text_copy_events", _upsert_text_copy),
    ("outbound_click", "outbound_click_events", _upsert_outbound_click),
    ("cta_click", "cta_click_events", _upsert_cta_click),
    ("tool_use", "tool_use_events", _upsert_tool_use),
    ("engagement_signal", "engagement_signals", _upsert_engagement_signal),
)


async def _backfill_one(
    client: Ga4Client,
    session,
    tenant_id: uuid.UUID,
    key: str,
    fetcher_attr: str,
    upserter,
    start: date,
    end: date,
) -> int:
    fetcher = getattr(client, fetcher_attr)
    total = 0
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        try:
            rows = await fetcher(cur, chunk_end)
        except Exception as exc:
            print(f"  {key:<18} {cur} 〜 {chunk_end}: ERROR {type(exc).__name__}: {exc}")
            cur = chunk_end + timedelta(days=1)
            continue
        if rows:
            await upserter(session, tenant_id, rows)
            await session.commit()
        total += len(rows)
        print(f"  {key:<18} {cur} 〜 {chunk_end}: {len(rows):>5} rows (cum {total})")
        cur = chunk_end + timedelta(days=1)
    return total


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--start", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    )
    parser.add_argument(
        "--end", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="--start 未指定時、過去 N 日。デフォルトは EVENT_LAUNCH_DATE 起点。",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help=f"特定の収集 key のみ実行(例: ai_crawler / cta_click)。"
        f" 利用可能: {', '.join(k for k, _, _ in COLLECTORS)}",
    )
    args = parser.parse_args()
    tenant_id = uuid.UUID(args.tenant_id)

    end = args.end or (date.today() - timedelta(days=1))
    if args.start:
        start = args.start
    elif args.days:
        start = end - timedelta(days=args.days - 1)
    else:
        start = EVENT_LAUNCH_DATE
    if start > end:
        raise SystemExit(f"start({start}) > end({end}) です。")

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

        print(f"window: {start} 〜 {end}")
        targets = [c for c in COLLECTORS if args.only is None or c[0] == args.only]
        if not targets:
            available = ", ".join(k for k, _, _ in COLLECTORS)
            raise SystemExit(
                f"--only {args.only!r} に該当する key がありません。利用可能: {available}"
            )

        for key, fetcher_attr, upserter in targets:
            print(f"--- {key} ---")
            n = await _backfill_one(
                client, session, tenant_id, key, fetcher_attr, upserter, start, end
            )
            print(f"{key} total: {n}")
            if SLEEP_BETWEEN_METHODS_SEC > 0:
                await asyncio.sleep(SLEEP_BETWEEN_METHODS_SEC)


if __name__ == "__main__":
    asyncio.run(main())
