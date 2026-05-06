"""add competitors.target_urls (text[])

Revision ID: c3d4e5f60189
Revises: c2b3c4d5e6f7
Create Date: 2026-05-06 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f60189"
down_revision: str | Sequence[str] | None = "c2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "competitors",
        sa.Column(
            "target_urls",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("competitors", "target_urls")
