"""add user profile fields and group avatar

Revision ID: 6d2f8f9f3c11
Revises: 280afe8735a1
Create Date: 2026-05-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d2f8f9f3c11"
down_revision: Union[str, None] = "280afe8735a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nickname", sa.String(), nullable=True))
    op.add_column("users", sa.Column("phone_number", sa.String(), nullable=True))
    op.execute(
        "UPDATE users SET nickname = COALESCE(NULLIF(TRIM(BOTH '@' FROM username), ''), email) "
        "WHERE nickname IS NULL OR nickname = ''"
    )
    op.alter_column("users", "nickname", existing_type=sa.String(), nullable=False)
    op.add_column("chats", sa.Column("avatar_photo", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("chats", "avatar_photo")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "nickname")
