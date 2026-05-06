"""add keyword_suggestions, keyword_universe, content_briefs

Revision ID: c1a2b3d4e5f6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-06 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1a2b3d4e5f6"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ------------------------------------------------------------
    # keyword_suggestions: 収集生データ
    # ------------------------------------------------------------
    op.create_table(
        "keyword_suggestions",
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("seed_keyword", sa.Text(), nullable=True),
        sa.Column("derived_keyword", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        "ix_kws_tenant_fetched",
        "keyword_suggestions",
        ["tenant_id", sa.text("fetched_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_kws_tenant_source",
        "keyword_suggestions",
        ["tenant_id", "source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_keyword_suggestions_tenant_id"),
        "keyword_suggestions",
        ["tenant_id"],
        unique=False,
    )
    # 検索高速化用(同日同 seed+derived の重複は収集ロジック側で抑止する)
    op.create_index(
        "ix_kws_tenant_seed_derived",
        "keyword_suggestions",
        ["tenant_id", "seed_keyword", "derived_keyword"],
        unique=False,
    )
    _enable_rls("keyword_suggestions")

    # ------------------------------------------------------------
    # keyword_universe: 集計済キーワード辞書
    # ------------------------------------------------------------
    op.create_table(
        "keyword_universe",
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("cluster_id", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column(
            "is_geographic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("gsc_imp_12m", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("gsc_clicks_12m", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("gsc_avg_position", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column(
            "suggest_derivative_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "competitor_coverage_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("llm_self_cite_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("llm_competitor_cite_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "priority_score",
            sa.Numeric(precision=6, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("opportunity_flag", sa.Text(), nullable=True),
        sa.Column(
            "source_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "last_aggregated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "keyword", name="uq_ku_tenant_keyword"),
    )
    op.create_index(
        "ix_ku_tenant_cluster",
        "keyword_universe",
        ["tenant_id", "cluster_id"],
        unique=False,
    )
    op.create_index(
        "ix_ku_tenant_priority",
        "keyword_universe",
        ["tenant_id", sa.text("priority_score DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_keyword_universe_tenant_id"),
        "keyword_universe",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("keyword_universe")

    # ------------------------------------------------------------
    # content_briefs: AI生成のコンテンツブリーフ
    # ------------------------------------------------------------
    op.create_table(
        "content_briefs",
        sa.Column("primary_keyword", sa.Text(), nullable=False),
        sa.Column("cluster_id", sa.Text(), nullable=False),
        sa.Column(
            "selected_keywords",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column(
            "h2_outline",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "related_keywords",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "competitor_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("target_url_slug", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("wp_draft_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cb_tenant_created",
        "content_briefs",
        ["tenant_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_cb_tenant_status",
        "content_briefs",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_briefs_tenant_id"),
        "content_briefs",
        ["tenant_id"],
        unique=False,
    )
    _enable_rls("content_briefs")


def downgrade() -> None:
    _disable_rls("content_briefs")
    op.drop_index(op.f("ix_content_briefs_tenant_id"), table_name="content_briefs")
    op.drop_index("ix_cb_tenant_status", table_name="content_briefs")
    op.drop_index("ix_cb_tenant_created", table_name="content_briefs")
    op.drop_table("content_briefs")

    _disable_rls("keyword_universe")
    op.drop_index(op.f("ix_keyword_universe_tenant_id"), table_name="keyword_universe")
    op.drop_index("ix_ku_tenant_priority", table_name="keyword_universe")
    op.drop_index("ix_ku_tenant_cluster", table_name="keyword_universe")
    op.drop_table("keyword_universe")

    _disable_rls("keyword_suggestions")
    op.drop_index("ix_kws_tenant_seed_derived", table_name="keyword_suggestions")
    op.drop_index(op.f("ix_keyword_suggestions_tenant_id"), table_name="keyword_suggestions")
    op.drop_index("ix_kws_tenant_source", table_name="keyword_suggestions")
    op.drop_index("ix_kws_tenant_fetched", table_name="keyword_suggestions")
    op.drop_table("keyword_suggestions")
