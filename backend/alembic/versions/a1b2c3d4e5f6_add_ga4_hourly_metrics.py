"""add ga4_hourly_metrics

Revision ID: a1b2c3d4e5f6
Revises: f7081234abcd
Create Date: 2026-05-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f7081234abcd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ga4_hourly_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hour", sa.SmallInteger(), nullable=False),
        sa.Column("sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("hour >= 0 AND hour <= 23", name="ck_ga4_hourly_hour_range"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "date", "hour", name="uq_ga4_hourly_tenant_date_hour"
        ),
    )
    op.create_index(
        "ix_ga4_hourly_tenant_date",
        "ga4_hourly_metrics",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_hourly_metrics_tenant_id"),
        "ga4_hourly_metrics",
        ["tenant_id"],
        unique=False,
    )

    op.execute("ALTER TABLE ga4_hourly_metrics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_hourly_metrics FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON ga4_hourly_metrics "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ga4_hourly_metrics")
    op.execute("ALTER TABLE ga4_hourly_metrics NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_hourly_metrics DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        op.f("ix_ga4_hourly_metrics_tenant_id"), table_name="ga4_hourly_metrics"
    )
    op.drop_index("ix_ga4_hourly_tenant_date", table_name="ga4_hourly_metrics")
    op.drop_table("ga4_hourly_metrics")
