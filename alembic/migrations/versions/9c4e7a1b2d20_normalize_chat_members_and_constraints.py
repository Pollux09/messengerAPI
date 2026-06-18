"""normalize chat members and constraints

Revision ID: 9c4e7a1b2d20
Revises: f2a9c6b4d110
Create Date: 2026-06-17 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c4e7a1b2d20"
down_revision: Union[str, None] = "f2a9c6b4d110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS title VARCHAR")
    op.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS avatar_photo VARCHAR")
    op.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS created_by UUID")
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS encrypted_aes_key_sender TEXT NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS encrypted_aes_key_receiver TEXT NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS encrypted_keys JSON NOT NULL DEFAULT '{}'::json"
    )
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS iv TEXT NOT NULL DEFAULT ''"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_members (
            chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )

    op.execute(
        """
        INSERT INTO chat_members (chat_id, user_id)
        SELECT chats.id, member_id
        FROM chats
        CROSS JOIN LATERAL unnest(chats.users_ids) AS member_id
        ON CONFLICT (chat_id, user_id) DO NOTHING
        """
    )

    op.execute("DROP INDEX IF EXISTS ix_chats_users_count")
    op.execute("ALTER TABLE chats DROP COLUMN IF EXISTS users_count")
    op.execute("ALTER TABLE chats DROP COLUMN IF EXISTS users_ids")

    op.execute("ALTER TABLE chats DROP CONSTRAINT IF EXISTS chats_created_by_fkey")
    op.create_foreign_key(
        "chats_created_by_fkey",
        "chats",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_user_id_fkey")
    op.create_foreign_key(
        "messages_user_id_fkey",
        "messages",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_crypto_keys_user_id ON crypto_keys (user_id)")


def downgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("users_count", sa.Integer(), nullable=True, server_default="2"),
    )
    op.add_column(
        "chats",
        sa.Column("users_ids", sa.ARRAY(sa.UUID()), nullable=True),
    )

    op.execute(
        """
        UPDATE chats
        SET users_ids = members.user_ids,
            users_count = COALESCE(cardinality(members.user_ids), 0)
        FROM (
            SELECT chat_id, array_agg(user_id ORDER BY user_id) AS user_ids
            FROM chat_members
            GROUP BY chat_id
        ) AS members
        WHERE chats.id = members.chat_id
        """
    )

    op.create_index(
        op.f("ix_chats_users_count"),
        "chats",
        ["users_count"],
        unique=False,
    )

    op.execute("DROP INDEX IF EXISTS ix_crypto_keys_user_id")

    op.execute("ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_user_id_fkey")
    op.create_foreign_key(
        "messages_user_id_fkey",
        "messages",
        "users",
        ["user_id"],
        ["id"],
    )

    op.execute("ALTER TABLE chats DROP CONSTRAINT IF EXISTS chats_created_by_fkey")
    op.create_foreign_key(
        "chats_created_by_fkey",
        "chats",
        "users",
        ["created_by"],
        ["id"],
    )

    op.drop_table("chat_members")
