"""add roles and registration statuses

Revision ID: b9d5a7df6e21
Revises: 6d2f8f9f3c11
Create Date: 2026-05-24 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9d5a7df6e21"
down_revision: Union[str, None] = "6d2f8f9f3c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_title"), "roles", ["title"], unique=True)

    op.add_column(
        "users",
        sa.Column(
            "registration_status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("users", sa.Column("rejection_reason", sa.String(), nullable=True))
    op.add_column("users", sa.Column("role_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE users SET registration_status = 'approved'")


def downgrade() -> None:
    op.drop_constraint("users_role_id_fkey", "users", type_="foreignkey")
    op.drop_column("users", "role_id")
    op.drop_column("users", "rejection_reason")
    op.drop_column("users", "registration_status")
    op.drop_index(op.f("ix_roles_title"), table_name="roles")
    op.drop_table("roles")
