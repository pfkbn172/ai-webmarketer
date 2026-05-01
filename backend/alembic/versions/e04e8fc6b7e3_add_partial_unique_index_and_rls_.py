"""add partial unique index and RLS policies

Revision ID: e04e8fc6b7e3
Revises: 484e47b6352a
Create Date: 2026-05-02 07:50:04.521708

設計指針 4.2 / implementation_plan 2.3 に従う:
- author_profiles に部分一意 INDEX(is_primary が true のもののみ tenant_id で unique)
- 全テナント所属テーブルに RLS を有効化、FORCE ROW LEVEL SECURITY、
  tenant_isolation ポリシーを適用
- ポリシー判定: tenant_id = current_setting('app.tenant_id', true)::uuid

リクエストごとに `SELECT set_config('app.tenant_id', '<uuid>', true)` を発行することで、
PostgreSQL の RLS が WHERE 句に自動付与される。app.tenant_id 未設定時は NULL となり、
すべてのテナントテーブル参照が拒否される(意図通り)。

job_execution_logs / audit_logs / users / user_tenants / prompt_templates は
管理者・システム横断テーブルのため RLS を適用しない。アプリ層で必要に応じて
tenant フィルタを行う。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e04e8fc6b7e3"
down_revision: str | Sequence[str] | None = "484e47b6352a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# RLS を適用するテーブル(全て tenant_id NOT NULL のテナント所属テーブル)
TENANT_TABLES: tuple[str, ...] = (
    "tenants",  # 自分自身も RLS で隔離(id = app.tenant_id)
    "tenant_credentials",
    "target_queries",
    "competitors",
    "author_profiles",
    "contents",
    "content_metrics",
    "citation_logs",
    "inquiries",
    "reports",
    "kpi_logs",
    "ai_provider_configs",
    "schema_audit_logs",
)


def _isolation_column(table: str) -> str:
    """tenants テーブルだけは判定カラムが id、他は tenant_id。"""
    return "id" if table == "tenants" else "tenant_id"


def upgrade() -> None:
    # 1. author_profiles: テナントごとに is_primary=true は最大 1 件
    op.execute(
        "CREATE UNIQUE INDEX uq_author_profiles_primary "
        "ON author_profiles(tenant_id) WHERE is_primary"
    )

    # 2. RLS 有効化 + ポリシー
    # NULLIF(..., '') で「未設定/空文字」を NULL に正規化してから uuid キャストする。
    # これにより RESET app.tenant_id 直後でも空文字 -> uuid キャスト失敗を起こさず、
    # 単に NULL となって全行が WHERE 不一致(=何も見えない)になる。
    for table in TENANT_TABLES:
        col = _isolation_column(table)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({col} = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            f"WITH CHECK ({col} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS uq_author_profiles_primary")
