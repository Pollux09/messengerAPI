"""add user last seen

Revision ID: c3a4a9c1d221
Revises: b9d5a7df6e21
Create Date: 2026-05-24 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a4a9c1d221"
down_revision: Union[str, None] = "b9d5a7df6e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
