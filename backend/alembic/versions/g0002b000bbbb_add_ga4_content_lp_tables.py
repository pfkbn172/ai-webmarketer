"""add ga4 content + lp tables (article_read_complete / text_copy / outbound_click / cta_click)

Revision ID: g0002b000bbbb
Revises: g0001a000aaaa
Create Date: 2026-05-11 12:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g0002b000bbbb"
down_revision: str | Sequence[str] | None = "g0001a000aaaa"
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
    # 5. ga4_article_read_complete_daily
    op.create_table(
        "ga4_article_read_complete_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page_path", sa.String(length=1024), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_views", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "date", "page_path", name="uq_ga4_arc_tenant_date_path"
        ),
    )
    op.create_index(
        "ix_ga4_arc_tenant_date",
        "ga4_article_read_complete_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_article_read_complete_daily_tenant_id"),
        "ga4_article_read_complete_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_article_read_complete_daily")

    # 6. ga4_text_copy_daily
    op.create_table(
        "ga4_text_copy_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page_path", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "page_path",
            "content_type",
            name="uq_ga4_txc_tenant_date_path_type",
        ),
    )
    op.create_index(
        "ix_ga4_txc_tenant_date",
        "ga4_text_copy_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_text_copy_daily_tenant_id"),
        "ga4_text_copy_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_text_copy_daily")

    # 7. ga4_outbound_click_daily
    op.create_table(
        "ga4_outbound_click_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("outbound_category", sa.String(length=32), nullable=False),
        sa.Column("link_domain", sa.String(length=255), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "outbound_category",
            "link_domain",
            name="uq_ga4_outb_tenant_date_cat_dom",
        ),
    )
    op.create_index(
        "ix_ga4_outb_tenant_date",
        "ga4_outbound_click_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_outbound_click_daily_tenant_id"),
        "ga4_outbound_click_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_outbound_click_daily")

    # 8. ga4_cta_click_daily
    op.create_table(
        "ga4_cta_click_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("lp_id", sa.String(length=128), nullable=False),
        sa.Column("cta_id", sa.String(length=64), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lp_sessions", sa.Integer(), server_default="0", nullable=False),
        *_common_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "date",
            "lp_id",
            "cta_id",
            name="uq_ga4_cta_tenant_date_lp_cta",
        ),
    )
    op.create_index(
        "ix_ga4_cta_tenant_date",
        "ga4_cta_click_daily",
        ["tenant_id", "date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ga4_cta_click_daily_tenant_id"),
        "ga4_cta_click_daily",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("ga4_cta_click_daily")


def downgrade() -> None:
    for table in (
        "ga4_cta_click_daily",
        "ga4_outbound_click_daily",
        "ga4_text_copy_daily",
        "ga4_article_read_complete_daily",
    ):
        _disable_rls(table)
        op.drop_table(table)
