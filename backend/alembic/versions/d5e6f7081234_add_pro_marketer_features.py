"""add pro-marketer features (page metrics, funnel amount, share token)

Revision ID: d5e6f7081234
Revises: c4d5e6f70123
Create Date: 2026-05-04 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7081234"
down_revision: str | Sequence[str] | None = "c4d5e6f70123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. inquiries.amount_yen
    op.add_column(
        "inquiries",
        sa.Column("amount_yen", sa.BigInteger(), nullable=True),
    )

    # 2. reports.share_token
    op.add_column(
        "reports",
        sa.Column("share_token", sa.String(length=48), nullable=True),
    )
    op.create_unique_constraint("uq_reports_share_token", "reports", ["share_token"])
    op.create_index("ix_reports_share_token", "reports", ["share_token"], unique=False)

    # 3. gsc_page_metrics
    op.create_table(
        "gsc_page_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page", sa.Text(), nullable=False),
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
            "tenant_id", "date", "page", name="uq_gsc_pm_tenant_date_page"
        ),
    )
    op.create_index(
        "ix_gsc_pm_tenant_date", "gsc_page_metrics", ["tenant_id", "date"], unique=False
    )
    op.create_index(
        "ix_gsc_pm_tenant_page", "gsc_page_metrics", ["tenant_id", "page"], unique=False
    )
    op.create_index(
        op.f("ix_gsc_page_metrics_tenant_id"), "gsc_page_metrics", ["tenant_id"], unique=False
    )
    op.execute("ALTER TABLE gsc_page_metrics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE gsc_page_metrics FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON gsc_page_metrics "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )

    # 4. ga4_page_daily
    op.create_table(
        "ga4_page_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page_path", sa.Text(), nullable=False),
        sa.Column("sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("users", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversions", sa.Integer(), server_default="0", nullable=False),
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
            "tenant_id", "date", "page_path", name="uq_ga4_pd_tenant_date_path"
        ),
    )
    op.create_index(
        "ix_ga4_pd_tenant_date", "ga4_page_daily", ["tenant_id", "date"], unique=False
    )
    op.create_index(
        "ix_ga4_pd_tenant_path", "ga4_page_daily", ["tenant_id", "page_path"], unique=False
    )
    op.create_index(
        op.f("ix_ga4_page_daily_tenant_id"), "ga4_page_daily", ["tenant_id"], unique=False
    )
    op.execute("ALTER TABLE ga4_page_daily ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_page_daily FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON ga4_page_daily "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ga4_page_daily")
    op.execute("ALTER TABLE ga4_page_daily NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ga4_page_daily DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_ga4_page_daily_tenant_id"), table_name="ga4_page_daily")
    op.drop_index("ix_ga4_pd_tenant_path", table_name="ga4_page_daily")
    op.drop_index("ix_ga4_pd_tenant_date", table_name="ga4_page_daily")
    op.drop_table("ga4_page_daily")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON gsc_page_metrics")
    op.execute("ALTER TABLE gsc_page_metrics NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE gsc_page_metrics DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_gsc_page_metrics_tenant_id"), table_name="gsc_page_metrics")
    op.drop_index("ix_gsc_pm_tenant_page", table_name="gsc_page_metrics")
    op.drop_index("ix_gsc_pm_tenant_date", table_name="gsc_page_metrics")
    op.drop_table("gsc_page_metrics")

    op.drop_index("ix_reports_share_token", table_name="reports")
    op.drop_constraint("uq_reports_share_token", "reports", type_="unique")
    op.drop_column("reports", "share_token")

    op.drop_column("inquiries", "amount_yen")
