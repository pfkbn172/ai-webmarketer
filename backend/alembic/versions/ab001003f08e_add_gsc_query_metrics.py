"""add gsc_query_metrics

Revision ID: ab001003f08e
Revises: e04e8fc6b7e3
Create Date: 2026-05-02 08:26:58.235561

W1-10 で追加した GSC クエリ別日次メトリクス用テーブル。RLS 適用。

注意: autogenerate は uq_author_profiles_primary(部分一意 INDEX)を毎回
"removed" と誤判定するため、その drop は本マイグレーションでは行わない。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ab001003f08e"
down_revision: str | Sequence[str] | None = "e04e8fc6b7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gsc_query_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ctr", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("position", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "date", "query_text", name="uq_gsc_qm_tenant_date_query"
        ),
    )
    op.create_index(
        "ix_gsc_qm_tenant_date", "gsc_query_metrics", ["tenant_id", "date"], unique=False
    )
    op.create_index(
        op.f("ix_gsc_query_metrics_tenant_id"),
        "gsc_query_metrics",
        ["tenant_id"],
        unique=False,
    )

    # 新規テナントテーブルにも RLS を適用(e04e8fc6b7e3 と同じポリシー)
    op.execute("ALTER TABLE gsc_query_metrics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE gsc_query_metrics FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON gsc_query_metrics "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON gsc_query_metrics")
    op.execute("ALTER TABLE gsc_query_metrics NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE gsc_query_metrics DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_gsc_query_metrics_tenant_id"), table_name="gsc_query_metrics")
    op.drop_index("ix_gsc_qm_tenant_date", table_name="gsc_query_metrics")
    op.drop_table("gsc_query_metrics")
