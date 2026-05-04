"""GSC 過去データを遡って取得し DB に upsert する。

GSC は 16 ヶ月分まで遡れる(API 仕様)。--days 480 で実質上限。
冪等(既存日次は UPSERT)。

使い方:
    cd backend
    .venv/bin/python -m scripts.backfill_gsc --tenant-id <UUID> --days 480

GSC API のレート制限(1200 req/min)があるので chunk_days で分割。
"""

import argparse
import asyncio
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.collectors.google_oauth import load_google_credentials
from app.collectors.gsc.client import GscClient
from app.db.models.enums import CredentialProviderEnum
from app.db.models.gsc_page_metric import GscPageMetric
from app.db.models.gsc_query_metric import GscQueryMetric
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


async def _upsert_query(session, tenant_id, rows):
    if not rows:
        return
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "query_text": r.query_text or "(unknown)",
            "clicks": r.clicks,
            "impressions": r.impressions,
            "ctr": r.ctr,
            "position": r.position,
        }
        for r in rows
        if r.query_text
    ]
    if not payload:
        return
    for i in range(0, len(payload), _BATCH):
        chunk = payload[i : i + _BATCH]
        stmt = pg_insert(GscQueryMetric).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gsc_qm_tenant_date_query",
            set_={
                "clicks": stmt.excluded.clicks,
                "impressions": stmt.excluded.impressions,
                "ctr": stmt.excluded.ctr,
                "position": stmt.excluded.position,
            },
        )
        await session.execute(stmt)


async def _upsert_page(session, tenant_id, rows):
    if not rows:
        return
    payload = [
        {
            "tenant_id": tenant_id,
            "date": r.date,
            "page": r.page,
            "clicks": r.clicks,
            "impressions": r.impressions,
            "ctr": r.ctr,
            "position": r.position,
        }
        for r in rows
        if r.page
    ]
    if not payload:
        return
    for i in range(0, len(payload), _BATCH):
        chunk = payload[i : i + _BATCH]
        stmt = pg_insert(GscPageMetric).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gsc_pm_tenant_date_page",
            set_={
                "clicks": stmt.excluded.clicks,
                "impressions": stmt.excluded.impressions,
                "ctr": stmt.excluded.ctr,
                "position": stmt.excluded.position,
            },
        )
        await session.execute(stmt)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--days", type=int, default=480, help="今日から何日遡るか(GSC 上限 ~480)")
    parser.add_argument("--chunk-days", type=int, default=30)
    args = parser.parse_args()

    tenant_id = uuid.UUID(args.tenant_id)
    end = date.today() - timedelta(days=2)  # GSC は確定遅延 2 日
    overall_start = end - timedelta(days=args.days - 1)

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    total_q = 0
    total_p = 0

    async with factory() as session:
        await _set_ctx(session, tenant_id)
        repo = TenantCredentialRepository(session)
        creds = await load_google_credentials(repo, tenant_id, CredentialProviderEnum.gsc)
        cred = (
            await session.scalars(
                select(TenantCredential).where(
                    TenantCredential.tenant_id == tenant_id,
                    TenantCredential.provider == CredentialProviderEnum.gsc,
                )
            )
        ).one_or_none()
        if cred is None:
            print("[error] GSC credential が見つかりません", file=sys.stderr)
            return 1
        payload = decrypt_json(cred.encrypted_data)
        site_url = payload.get("site_url")
        if not site_url:
            print("[error] site_url が登録されていません", file=sys.stderr)
            return 1
        client = GscClient(creds, site_url=site_url)

        cursor = end
        while cursor >= overall_start:
            chunk_end = cursor
            chunk_start = max(overall_start, chunk_end - timedelta(days=args.chunk_days - 1))
            print(f"[gsc] {chunk_start} - {chunk_end} を取得中…", flush=True)
            try:
                qrows = await client.query_metrics(
                    chunk_start, chunk_end, dimensions=["date", "query"], row_limit=5000
                )
                prows = await client.query_metrics(
                    chunk_start, chunk_end, dimensions=["date", "page"], row_limit=5000
                )
            except Exception as e:
                print(f"[gsc] 取得失敗 ({chunk_start}-{chunk_end}): {e}", file=sys.stderr)
                break
            await _upsert_query(session, tenant_id, qrows)
            await _upsert_page(session, tenant_id, prows)
            await session.commit()
            await _set_ctx(session, tenant_id)
            total_q += len(qrows)
            total_p += len(prows)
            cursor = chunk_start - timedelta(days=1)

    await engine.dispose()
    print(f"[gsc] 完了: query_rows={total_q}, page_rows={total_p}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
