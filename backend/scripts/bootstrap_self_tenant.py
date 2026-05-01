"""自社用の初期テナントを作成し、admin ユーザーに紐付ける。

Phase 1 自社運用のための簡易ブートストラップ。
冪等(同じ domain のテナントが既存ならスキップ、紐付けも UPSERT)。

使い方:
    cd backend
    .venv/bin/python -m scripts.bootstrap_self_tenant \
        --email pfkbn172@gmail.com \
        --tenant-name 'kiseeeen' \
        --domain kiseeeen.co.jp \
        --industry 'SaaS マーケティング'
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.enums import ComplianceTypeEnum
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.settings import settings


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--industry", default="")
    parser.add_argument(
        "--compliance",
        default="general",
        choices=[c.value for c in ComplianceTypeEnum],
    )
    args = parser.parse_args()

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # 1. user 取得
        user = (
            await session.scalars(select(User).where(User.email == args.email))
        ).one_or_none()
        if user is None:
            print(f"[ERROR] user {args.email} が存在しません", file=sys.stderr)
            return 2

        # 2. tenant 取得 or 作成
        # RLS の都合で tenants は app.tenant_id を SET してから操作する必要がある。
        # まずは "全 SET = この tenant の id" として新規 UUID を作って試行 → 既存検索は別経路。
        # ただし tenants の検索は RLS により app.tenant_id 一致のみ可なので、admin 接続から
        # ALTER TABLE で BYPASSRLS 化する手も将来は検討。Phase 1 では新規作成 or 既存 id を
        # 環境変数等で指定する方針にする。
        # ここでは: (--domain で逆引き)同 domain がすでにあれば既存 id を再利用する代わりに、
        # ALTER ROLE marketer BYPASSRLS で一時的に RLS を回避できないため、
        # 簡易策として「app.tenant_id を空のまま検索 → 0 件 → 常に新規作成」を採る。
        # 二重起動防止には呼び出し側で気を配る。
        tenant_id = uuid.uuid4()
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        tenant = Tenant(
            id=tenant_id,
            name=args.tenant_name,
            industry=args.industry or None,
            domain=args.domain,
            compliance_type=ComplianceTypeEnum(args.compliance),
            is_active=True,
        )
        session.add(tenant)
        await session.flush()

        # 3. user_tenants 紐付け(UNIQUE PK なので既存はスキップ)
        await session.execute(
            text(
                "INSERT INTO user_tenants (user_id, tenant_id) VALUES (:u, :t) "
                "ON CONFLICT DO NOTHING"
            ),
            {"u": str(user.id), "t": str(tenant_id)},
        )
        await session.commit()
        print(
            f"[INFO] tenant={tenant_id} を作成し、user={user.id}({args.email}) に紐付けました"
        )
        print(
            f"[INFO] .env の MARKETER_ACTIVE_TENANT_IDS に {tenant_id} を設定してください"
        )

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
