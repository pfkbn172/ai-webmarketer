"""add ga4_ai_referral_daily

Revision ID: c4d5e6f70123
Revises: f6da5caf3105
Create Date: 2026-05-04 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f70123"
down_revision: str | Sequence[str] | None = "f6da5caf3105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ga4_ai_referral_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source_host", sa.String(length=255), nullable=False),
        sa.Column("sessions", sa.Integer(), server_default="0", nullable=False),
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
            "tenant_id", "date", "source_host", name="uq_ga4_ai_ref_tenant_date_host"
        ),
    )
    op.create_index(
        "ix_ga4_ai_ref_tenant_date",
        "ga4_ai_referral_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_ai_referral_daily_tenant_id"),
        "ga4_ai_referral_daily",
        ["tenant_id"],
        unique=False,
    )

    op.execute("ALTER TABLE ga4_ai_referral_daily ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_ai_referral_daily FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON ga4_ai_referral_daily "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ga4_ai_referral_daily")
    op.execute("ALTER TABLE ga4_ai_referral_daily NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_ai_referral_daily DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        op.f("ix_ga4_ai_referral_daily_tenant_id"), table_name="ga4_ai_referral_daily"
    )
    op.drop_index("ix_ga4_ai_ref_tenant_date", table_name="ga4_ai_referral_daily")
    op.drop_table("ga4_ai_referral_daily")
