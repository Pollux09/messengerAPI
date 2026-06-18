"""drop unused chat_types table

Revision ID: f2a9c6b4d110
Revises: e7b1e2c4d001
Create Date: 2026-06-17 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a9c6b4d110"
down_revision: Union[str, None] = "e7b1e2c4d001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("chat_types")


def downgrade() -> None:
    op.create_table(
        "chat_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
