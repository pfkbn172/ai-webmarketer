"""add page_speed_metrics

Revision ID: f7081234abcd
Revises: e6f7081234ab
Create Date: 2026-05-05 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7081234abcd"
down_revision: str | Sequence[str] | None = "e6f7081234ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_speed_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("strategy", sa.Text(), nullable=False),
        sa.Column("performance_score", sa.Integer(), nullable=True),
        sa.Column("lcp_ms", sa.Integer(), nullable=True),
        sa.Column("cls", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("inp_ms", sa.Integer(), nullable=True),
        sa.Column("fcp_ms", sa.Integer(), nullable=True),
        sa.Column("ttfb_ms", sa.Integer(), nullable=True),
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
            "tenant_id", "date", "page_url", "strategy",
            name="uq_psm_tenant_date_url_strategy",
        ),
    )
    op.create_index("ix_psm_tenant_date", "page_speed_metrics", ["tenant_id", "date"], unique=False)
    op.create_index(
        op.f("ix_page_speed_metrics_tenant_id"),
        "page_speed_metrics",
        ["tenant_id"],
        unique=False,
    )

    op.execute("ALTER TABLE page_speed_metrics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE page_speed_metrics FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON page_speed_metrics "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON page_speed_metrics")
    op.execute("ALTER TABLE page_speed_metrics NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE page_speed_metrics DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_page_speed_metrics_tenant_id"), table_name="page_speed_metrics")
    op.drop_index("ix_psm_tenant_date", table_name="page_speed_metrics")
    op.drop_table("page_speed_metrics")
