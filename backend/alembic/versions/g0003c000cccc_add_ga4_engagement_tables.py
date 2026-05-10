"""add ga4 engagement tables (tool_use / engagement_signal)

Revision ID: g0003c000cccc
Revises: g0002b000bbbb
Create Date: 2026-05-11 12:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g0003c000cccc"
down_revision: str | Sequence[str] | None = "g0002b000bbbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_columns() -> list[sa.Column]:
    return [
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
    ]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # 9. ga4_tool_use_daily
    op.create_table(
        "ga4_tool_use_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "date", "tool_name", name="uq_ga4_tool_tenant_date_name"
        ),
    )
    op.create_index(
        "ix_ga4_tool_tenant_date",
        "ga4_tool_use_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_tool_use_daily_tenant_id"),
        "ga4_tool_use_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_tool_use_daily")

    # 10. ga4_engagement_signal_daily
    op.create_table(
        "ga4_engagement_signal_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("sub_key", sa.String(length=255), server_default="-", nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "event_name",
            "sub_key",
            name="uq_ga4_engsig_tenant_date_evt_sub",
        ),
    )
    op.create_index(
        "ix_ga4_engsig_tenant_date",
        "ga4_engagement_signal_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        "ix_ga4_engsig_tenant_date_evt",
        "ga4_engagement_signal_daily",
        ["tenant_id", "date", "event_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_engagement_signal_daily_tenant_id"),
        "ga4_engagement_signal_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_engagement_signal_daily")


def downgrade() -> None:
    for table in ("ga4_engagement_signal_daily", "ga4_tool_use_daily"):
        _disable_rls(table)
        op.drop_table(table)
