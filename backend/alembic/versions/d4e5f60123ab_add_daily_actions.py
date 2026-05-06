"""add daily_actions

Revision ID: d4e5f60123ab
Revises: c3d4e5f60189
Create Date: 2026-05-06 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f60123ab"
down_revision: str | Sequence[str] | None = "c3d4e5f60189"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_actions",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action_index", sa.Integer(), nullable=False),  # 1〜3
        sa.Column("title", sa.Text(), nullable=False),
        # 'red' = 最優先, 'yellow' = 推奨, 'green' = 余力があれば
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        # フロントの遷移先(例: '/strategy/universe?keyword=...', '/production/briefs/new?...')
        sa.Column("target_url", sa.Text(), nullable=True),
        # 関連キーワード(あれば。フロントでハイライト用)
        sa.Column("related_keyword", sa.Text(), nullable=True),
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
    )
    op.create_index(
        "ix_da_tenant_generated",
        "daily_actions",
        ["tenant_id", sa.text("generated_at DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_actions_tenant_id"),
        "daily_actions",
        ["tenant_id"],
        unique=False,
    )

    op.execute("ALTER TABLE daily_actions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE daily_actions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON daily_actions "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON daily_actions")
    op.execute("ALTER TABLE daily_actions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE daily_actions DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_daily_actions_tenant_id"), table_name="daily_actions")
    op.drop_index("ix_da_tenant_generated", table_name="daily_actions")
    op.drop_table("daily_actions")
