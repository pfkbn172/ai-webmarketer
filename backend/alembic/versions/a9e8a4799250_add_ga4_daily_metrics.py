"""add ga4_daily_metrics

Revision ID: a9e8a4799250
Revises: ab001003f08e
Create Date: 2026-05-02 08:29:09.104285
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9e8a4799250"
down_revision: str | Sequence[str] | None = "ab001003f08e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ga4_daily_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("users", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bounce_rate", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("conversions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("organic_sessions", sa.Integer(), server_default="0", nullable=False),
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
        sa.UniqueConstraint("tenant_id", "date", name="uq_ga4_daily_tenant_date"),
    )
    op.create_index(
        "ix_ga4_daily_tenant_date", "ga4_daily_metrics", ["tenant_id", "date"], unique=False
    )
    op.create_index(
        op.f("ix_ga4_daily_metrics_tenant_id"),
        "ga4_daily_metrics",
        ["tenant_id"],
        unique=False,
    )

    op.execute("ALTER TABLE ga4_daily_metrics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_daily_metrics FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON ga4_daily_metrics "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ga4_daily_metrics")
    op.execute("ALTER TABLE ga4_daily_metrics NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_daily_metrics DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_ga4_daily_metrics_tenant_id"), table_name="ga4_daily_metrics")
    op.drop_index("ix_ga4_daily_tenant_date", table_name="ga4_daily_metrics")
    op.drop_table("ga4_daily_metrics")
