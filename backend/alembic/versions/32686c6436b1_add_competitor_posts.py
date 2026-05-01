"""add competitor_posts

Revision ID: 32686c6436b1
Revises: a9e8a4799250
Create Date: 2026-05-02 08:42:04.815384
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "32686c6436b1"
down_revision: str | Sequence[str] | None = "a9e8a4799250"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitor_posts",
        sa.Column("competitor_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competitor_id", "url", name="uq_competitor_posts_url"),
    )
    op.create_index(
        "ix_competitor_posts_tenant_published",
        "competitor_posts",
        ["tenant_id", "published_at"],
    )
    op.create_index(
        op.f("ix_competitor_posts_tenant_id"), "competitor_posts", ["tenant_id"]
    )

    op.execute("ALTER TABLE competitor_posts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE competitor_posts FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON competitor_posts "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON competitor_posts")
    op.execute("ALTER TABLE competitor_posts NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE competitor_posts DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_competitor_posts_tenant_id"), table_name="competitor_posts")
    op.drop_index("ix_competitor_posts_tenant_published", table_name="competitor_posts")
    op.drop_table("competitor_posts")
