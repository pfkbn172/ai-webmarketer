"""add ga4 aio tables (ai_referral_event / ai_crawler / ai_crawler_page / llms_txt_fetch)

Revision ID: g0001a000aaaa
Revises: d4e5f60123ab
Create Date: 2026-05-11 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g0001a000aaaa"
down_revision: str | Sequence[str] | None = "d4e5f60123ab"
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
    # 1. ga4_ai_referral_event_daily
    op.create_table(
        "ga4_ai_referral_event_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ai_referrer_domain", sa.String(length=255), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "ai_referrer_domain",
            name="uq_ga4_ai_ref_evt_tenant_date_dom",
        ),
    )
    op.create_index(
        "ix_ga4_ai_ref_evt_tenant_date",
        "ga4_ai_referral_event_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_ai_referral_event_daily_tenant_id"),
        "ga4_ai_referral_event_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_ai_referral_event_daily")

    # 2. ga4_ai_crawler_daily
    op.create_table(
        "ga4_ai_crawler_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("crawler_name", sa.String(length=128), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "crawler_name",
            name="uq_ga4_ai_crawl_tenant_date_name",
        ),
    )
    op.create_index(
        "ix_ga4_ai_crawl_tenant_date",
        "ga4_ai_crawler_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_ai_crawler_daily_tenant_id"),
        "ga4_ai_crawler_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_ai_crawler_daily")

    # 3. ga4_ai_crawler_page_daily
    op.create_table(
        "ga4_ai_crawler_page_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("crawler_name", sa.String(length=128), nullable=False),
        sa.Column("page_path", sa.String(length=1024), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "crawler_name",
            "page_path",
            name="uq_ga4_ai_crawl_pg_tenant_date_name_path",
        ),
    )
    op.create_index(
        "ix_ga4_ai_crawl_pg_tenant_date",
        "ga4_ai_crawler_page_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        "ix_ga4_ai_crawl_pg_tenant_date_name",
        "ga4_ai_crawler_page_daily",
        ["tenant_id", "date", "crawler_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_ai_crawler_page_daily_tenant_id"),
        "ga4_ai_crawler_page_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_ai_crawler_page_daily")

    # 4. ga4_llms_txt_fetch_daily
    op.create_table(
        "ga4_llms_txt_fetch_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("crawler_name", sa.String(length=128), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "date", "crawler_name", name="uq_ga4_llms_tenant_date_name"
        ),
    )
    op.create_index(
        "ix_ga4_llms_tenant_date",
        "ga4_llms_txt_fetch_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_llms_txt_fetch_daily_tenant_id"),
        "ga4_llms_txt_fetch_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_llms_txt_fetch_daily")


def downgrade() -> None:
    for table in (
        "ga4_llms_txt_fetch_daily",
        "ga4_ai_crawler_page_daily",
        "ga4_ai_crawler_daily",
        "ga4_ai_referral_event_daily",
    ):
        _disable_rls(table)
        op.drop_table(table)
