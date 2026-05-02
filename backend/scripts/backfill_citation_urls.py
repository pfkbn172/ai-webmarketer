"""既存 citation_logs のラッパー URL を実 URL に展開し、self_cited / competitor_cited を再判定する。

Gemini Grounding ラッパー URL は HEAD/GET でリダイレクト先に解決可能。
既に保管された citation_logs は古いコードで判定済(self_cited が常に false)
のため、本スクリプトで一括バックフィルする。

API 呼び出しは Gemini ではなく vertexaisearch.cloud.google.com への HEAD/GET のみで、
LLM の API キー消費はゼロ。

使い方:
    cd backend
    .venv/bin/python -m scripts.backfill_citation_urls --tenant-id <uuid>
    # オプション
    --since 2026-04-01    指定日以降の citation_logs のみ対象
    --dry-run             変更を保存せずに差分表示のみ
"""

import argparse
import asyncio
import sys
import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.collectors.llm_citation.gemini_client import _resolve_wrapper_urls
from app.collectors.llm_citation.matcher import MatchProfile, evaluate
from app.db.models.citation_log import CitationLog
from app.db.models.competitor import Competitor
from app.db.models.tenant import Tenant
from app.settings import settings


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--since", help="YYYY-MM-DD 以降の citation_logs のみ対象")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tenant_uuid = uuid.UUID(args.tenant_id)
    since_date = date.fromisoformat(args.since) if args.since else None

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    updated = 0
    examined = 0
    self_cited_added = 0

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"),
            {"t": str(tenant_uuid)},
        )

        tenant = (
            await session.scalars(select(Tenant).where(Tenant.id == tenant_uuid))
        ).one()
        competitors = list(
            (
                await session.scalars(
                    select(Competitor).where(Competitor.is_active.is_(True))
                )
            ).all()
        )
        profile = MatchProfile(
            self_domain=tenant.domain,
            self_aliases=[tenant.name],
            competitor_domains=[c.domain for c in competitors],
        )

        stmt = select(CitationLog)
        if since_date:
            stmt = stmt.where(CitationLog.query_date >= since_date)
        rows = list((await session.scalars(stmt)).all())

        for row in rows:
            examined += 1
            old_urls: list[str] = list(row.cited_urls or [])
            if not any("vertexaisearch.cloud.google.com" in u for u in old_urls):
                continue
            new_urls = await _resolve_wrapper_urls(old_urls, domain_hints=[])
            if new_urls == old_urls:
                continue
            new_match = evaluate(row.response_text or "", new_urls, profile)
            if args.dry_run:
                print(
                    f"[DRY] {row.id} llm={row.llm_provider.value} "
                    f"self_cited={row.self_cited}->{new_match.self_cited} "
                    f"urls={len(old_urls)}->{len(new_urls)}"
                )
            else:
                row.cited_urls = new_urls
                row.self_cited = new_match.self_cited
                row.competitor_cited = new_match.competitor_cited
            updated += 1
            if new_match.self_cited and not row.self_cited:
                self_cited_added += 1

        if not args.dry_run:
            await session.commit()

    await engine.dispose()
    print(f"[DONE] examined={examined} updated={updated} new_self_cited={self_cited_added}")
    if args.dry_run:
        print("(dry-run のため DB は変更していません)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
