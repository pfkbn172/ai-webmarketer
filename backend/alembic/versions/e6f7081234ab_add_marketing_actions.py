"""add marketing_actions

Revision ID: e6f7081234ab
Revises: d5e6f7081234
Create Date: 2026-05-04 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7081234ab"
down_revision: str | Sequence[str] | None = "d5e6f7081234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketing_actions",
        sa.Column("action_date", sa.Date(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "content_publish",
                "seo_optimize",
                "ad_campaign",
                "pr",
                "event",
                "other",
                name="marketing_action_category",
            ),
            server_default="other",
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        "ix_marketing_actions_tenant_date",
        "marketing_actions",
        ["tenant_id", "action_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_marketing_actions_tenant_id"),
        "marketing_actions",
        ["tenant_id"],
        unique=False,
    )

    op.execute("ALTER TABLE marketing_actions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE marketing_actions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON marketing_actions "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON marketing_actions")
    op.execute("ALTER TABLE marketing_actions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE marketing_actions DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_marketing_actions_tenant_id"), table_name="marketing_actions")
    op.drop_index("ix_marketing_actions_tenant_date", table_name="marketing_actions")
    op.drop_table("marketing_actions")
    op.execute("DROP TYPE marketing_action_category")
