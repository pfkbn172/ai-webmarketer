"""add ga4_referral_daily and ga4_referral_hourly

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def _drop_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "ga4_referral_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("medium", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "source",
            "medium",
            name="uq_ga4_ref_d_tenant_date_src_med",
        ),
    )
    op.create_index(
        "ix_ga4_ref_d_tenant_date",
        "ga4_referral_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_referral_daily_tenant_id"),
        "ga4_referral_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_referral_daily")

    op.create_table(
        "ga4_referral_hourly",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hour", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("medium", sa.String(length=64), nullable=False),
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
        sa.CheckConstraint(
            "hour >= 0 AND hour <= 23", name="ck_ga4_ref_h_hour_range"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "hour",
            "source",
            "medium",
            name="uq_ga4_ref_h_tenant_date_hour_src_med",
        ),
    )
    op.create_index(
        "ix_ga4_ref_h_tenant_date",
        "ga4_referral_hourly",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_referral_hourly_tenant_id"),
        "ga4_referral_hourly",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_referral_hourly")


def downgrade() -> None:
    _drop_rls("ga4_referral_hourly")
    op.drop_index(
        op.f("ix_ga4_referral_hourly_tenant_id"), table_name="ga4_referral_hourly"
    )
    op.drop_index("ix_ga4_ref_h_tenant_date", table_name="ga4_referral_hourly")
    op.drop_table("ga4_referral_hourly")

    _drop_rls("ga4_referral_daily")
    op.drop_index(
        op.f("ix_ga4_referral_daily_tenant_id"), table_name="ga4_referral_daily"
    )
    op.drop_index("ix_ga4_ref_d_tenant_date", table_name="ga4_referral_daily")
    op.drop_table("ga4_referral_daily")
