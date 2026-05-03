"""add tenants.business_context jsonb

Revision ID: f6da5caf3105
Revises: 8046c6bb04f2
Create Date: 2026-05-03 10:57:14.372204
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6da5caf3105"
down_revision: str | Sequence[str] | None = "8046c6bb04f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "business_context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "business_context")
