"""ターゲットクエリを 1 テナント分まるごと入れ替える CLI。

Phase 1 自社運用の途中で、当初の広域クエリ(「中小企業 DX コンサル」等)から
実証データに基づく「地域 × IT/DX サポート」中心の戦略的クエリ群へ切り替える
ために作成。

挙動:
- --dry-run なら現状の登録件数と新規登録予定だけ表示
- 通常実行: 既存 target_queries を全削除 → 引数の YAML/JSON を読んで新規登録
- citation_logs は target_queries への FK CASCADE で自動削除される

引数:
- --tenant-id <uuid>            必須
- --queries-json <path>         JSON 配列(各要素に query_text, cluster_id, priority,
                                expected_conversion 等)
- --dry-run                     確認のみ

JSON 例:
[
  {"query_text": "平野区 IT DX サポート", "cluster_id": "local_district",
   "priority": 4, "expected_conversion": 4},
  {"query_text": "大阪市内 中小企業 DX サポート", "cluster_id": "local_metro",
   "priority": 4, "expected_conversion": 3}
]

戦略意図(Phase 1.5 切替時):
- 第 1 層 cluster_id="local_district" : 既に勝てている地域(天王寺/平野/阿倍野/東住吉)
- 第 2 層 cluster_id="local_expand"   : 拡大目標地域(生野/中央/東大阪/八尾/浪速)
- 第 3 層 cluster_id="industry_test"  : 業種特化(コンテンツ拡充の効果測定用)
- 第 4 層 cluster_id="competitive"    : 比較・競合観測
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.target_query import TargetQuery
from app.settings import settings


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--queries-json", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.queries_json.exists():
        print(f"[ERROR] {args.queries_json} が見つかりません", file=sys.stderr)
        return 2

    new_queries = json.loads(args.queries_json.read_text(encoding="utf-8"))
    if not isinstance(new_queries, list) or not new_queries:
        print("[ERROR] queries-json は非空の配列である必要があります", file=sys.stderr)
        return 2

    tenant_uuid = uuid.UUID(args.tenant_id)
    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_uuid)},
        )

        existing = list(
            (
                await session.scalars(
                    select(TargetQuery).where(TargetQuery.tenant_id == tenant_uuid)
                )
            ).all()
        )
        print(f"[INFO] 現在の登録数: {len(existing)} 件")
        for q in existing:
            print(f"  - {q.query_text} (cluster={q.cluster_id})")
        print(f"[INFO] 新規登録予定: {len(new_queries)} 件")
        for q in new_queries:
            print(f"  + {q['query_text']} (cluster={q.get('cluster_id', '-')})")

        if args.dry_run:
            print("[DRY] 実 DB は変更していません")
            await engine.dispose()
            return 0

        # 1) 既存 target_queries を一括削除(citation_logs は FK CASCADE で自動削除)
        deleted_count = (
            await session.execute(
                text("DELETE FROM target_queries WHERE tenant_id = :tid"),
                {"tid": str(tenant_uuid)},
            )
        ).rowcount
        print(f"[INFO] 既存 {deleted_count} 件を削除")

        # 2) 新規登録
        for q in new_queries:
            row = TargetQuery(
                tenant_id=tenant_uuid,
                query_text=q["query_text"],
                cluster_id=q.get("cluster_id"),
                priority=q.get("priority", 3),
                expected_conversion=q.get("expected_conversion", 3),
                search_intent=q.get("search_intent"),
                is_active=q.get("is_active", True),
            )
            session.add(row)
        await session.commit()
        print(f"[DONE] {len(new_queries)} 件を新規登録")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
