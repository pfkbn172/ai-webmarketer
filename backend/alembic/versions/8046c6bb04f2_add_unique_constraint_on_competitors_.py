"""add unique constraint on competitors and dedup

Revision ID: 8046c6bb04f2
Revises: 32686c6436b1
Create Date: 2026-05-02 23:57:14.962262

事前に (tenant_id, domain) で重複している既存行を削除してから UNIQUE 制約を追加する。
削除は「同一 (tenant_id, domain) で created_at が最も古い 1 件を残し他は削除」のルール。
重複が無ければ DELETE は 0 件で何もしない。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8046c6bb04f2"
down_revision: str | Sequence[str] | None = "32686c6436b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 既存重複削除(各 tenant_id+domain で最古の id を残す)
    op.execute(
        """
        DELETE FROM competitors c
        USING competitors c2
        WHERE c.tenant_id = c2.tenant_id
          AND c.domain = c2.domain
          AND c.id <> c2.id
          AND c2.id < c.id
        """
    )
    op.create_unique_constraint(
        "uq_competitors_tenant_domain",
        "competitors",
        ["tenant_id", "domain"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_competitors_tenant_domain", "competitors", type_="unique")
