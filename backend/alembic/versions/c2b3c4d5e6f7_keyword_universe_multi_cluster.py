"""keyword_universe: cluster_id -> cluster_ids text[] (multi-cluster)

Revision ID: c2b3c4d5e6f7
Revises: c1a2b3d4e5f6
Create Date: 2026-05-06 13:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) cluster_ids text[] を追加(NOT NULL DEFAULT '{}')
    op.add_column(
        "keyword_universe",
        sa.Column(
            "cluster_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )

    # 2) 既存 cluster_id の値を ARRAY[cluster_id] にコピー
    op.execute(
        "UPDATE keyword_universe SET cluster_ids = ARRAY[cluster_id] "
        "WHERE cluster_id IS NOT NULL AND cluster_id <> ''"
    )

    # 3) 旧 cluster_id を削除する前に、参照していたインデックスを落とす
    op.drop_index("ix_ku_tenant_cluster", table_name="keyword_universe")

    # 4) 新インデックス(GIN を cluster_ids 単独で。tenant_id 絞り込みは
    #    既存 ix_keyword_universe_tenant_id とプランナの bitmap and 結合に任せる)
    op.execute(
        "CREATE INDEX ix_ku_clusters_gin ON keyword_universe USING GIN (cluster_ids)"
    )

    # 5) 旧 cluster_id 列を削除
    op.drop_column("keyword_universe", "cluster_id")

    # ---------------- content_briefs も合わせて配列対応 ----------------
    op.add_column(
        "content_briefs",
        sa.Column(
            "cluster_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )
    op.execute(
        "UPDATE content_briefs SET cluster_ids = ARRAY[cluster_id] "
        "WHERE cluster_id IS NOT NULL AND cluster_id <> ''"
    )
    op.drop_column("content_briefs", "cluster_id")


def downgrade() -> None:
    # content_briefs ロールバック(NOT NULL を後付けする際は先に値を埋める)
    op.add_column(
        "content_briefs",
        sa.Column("cluster_id", sa.Text(), server_default="", nullable=False),
    )
    op.execute(
        "UPDATE content_briefs SET cluster_id = COALESCE(cluster_ids[1], '')"
    )
    op.alter_column("content_briefs", "cluster_id", server_default=None)
    op.drop_column("content_briefs", "cluster_ids")

    # keyword_universe ロールバック
    op.add_column(
        "keyword_universe",
        sa.Column(
            "cluster_id", sa.Text(), server_default="unclassified", nullable=False
        ),
    )
    op.execute(
        "UPDATE keyword_universe SET cluster_id = COALESCE(cluster_ids[1], 'unclassified')"
    )
    op.alter_column("keyword_universe", "cluster_id", server_default=None)

    op.execute("DROP INDEX IF EXISTS ix_ku_clusters_gin")
    op.create_index(
        "ix_ku_tenant_cluster",
        "keyword_universe",
        ["tenant_id", "cluster_id"],
        unique=False,
    )
    op.drop_column("keyword_universe", "cluster_ids")
