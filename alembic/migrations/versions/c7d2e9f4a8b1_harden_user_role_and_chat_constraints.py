"""harden user role and chat constraints

Revision ID: c7d2e9f4a8b1
Revises: 9c4e7a1b2d20
Create Date: 2026-06-17 21:35:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d2e9f4a8b1"
down_revision: Union[str, None] = "9c4e7a1b2d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
    )


def _ensure_role(bind, *, title: str, is_admin: bool) -> uuid.UUID:
    existing_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE lower(title) = lower(:title)"),
        {"title": title},
    ).scalar()
    if existing_id is not None:
        bind.execute(
            sa.text(
                """
                UPDATE roles
                SET is_admin = :is_admin,
                    is_default = TRUE
                WHERE id = :role_id
                """
            ),
            {"role_id": existing_id, "is_admin": is_admin},
        )
        return existing_id

    role_id = uuid.uuid4()
    bind.execute(
        sa.text(
            """
            INSERT INTO roles (id, title, is_admin, is_default)
            VALUES (:id, :title, :is_admin, TRUE)
            """
        ),
        {"id": role_id, "title": title, "is_admin": is_admin},
    )
    return role_id


def upgrade() -> None:
    bind = op.get_bind()
    admin_role_id = _ensure_role(bind, title="Админ", is_admin=True)
    user_role_id = _ensure_role(bind, title="Пользователь", is_admin=False)

    if _has_column(bind, "users", "is_admin"):
        bind.execute(
            sa.text(
                """
                UPDATE users
                SET role_id = CASE
                    WHEN is_admin THEN CAST(:admin_role_id AS UUID)
                    ELSE CAST(:user_role_id AS UUID)
                END
                WHERE role_id IS NULL
                """
            ),
            {
                "admin_role_id": admin_role_id,
                "user_role_id": user_role_id,
            },
        )

    bind.execute(
        sa.text(
            """
            UPDATE users
            SET role_id = CAST(:user_role_id AS UUID)
            WHERE role_id IS NULL
            """
        ),
        {"user_role_id": user_role_id},
    )

    op.execute("DROP TABLE IF EXISTS chat_types")
    op.execute("DROP INDEX IF EXISTS ix_chats_users_count")
    op.execute("ALTER TABLE chats DROP COLUMN IF EXISTS users_count")
    op.execute("ALTER TABLE chats DROP COLUMN IF EXISTS users_ids")

    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN username SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN hashed_password SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN role_id SET NOT NULL")
    op.execute("ALTER TABLE chats ALTER COLUMN type SET NOT NULL")
    op.execute("ALTER TABLE messages ALTER COLUMN created_at SET NOT NULL")

    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_id_fkey")
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_registration_status")
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT ck_users_registration_status
        CHECK (registration_status IN ('pending', 'approved', 'rejected'))
        """
    )

    op.execute("ALTER TABLE chats DROP CONSTRAINT IF EXISTS ck_chats_type")
    op.execute(
        """
        ALTER TABLE chats
        ADD CONSTRAINT ck_chats_type
        CHECK (type IN ('private', 'group'))
        """
    )

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_crypto_keys_user_id ON crypto_keys (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_members_user_id ON chat_members (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_chat_id_created_at ON messages (chat_id, created_at)")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_admin")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute(
        """
        UPDATE users
        SET is_admin = COALESCE(roles.is_admin, FALSE)
        FROM roles
        WHERE roles.id = users.role_id
        """
    )

    op.execute("DROP INDEX IF EXISTS ix_messages_chat_id_created_at")
    op.execute("DROP INDEX IF EXISTS ix_chat_members_user_id")
    op.execute("ALTER TABLE chats DROP CONSTRAINT IF EXISTS ck_chats_type")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_registration_status")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_id_fkey")
    op.create_foreign_key(
        "users_role_id_fkey",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("ALTER TABLE users ALTER COLUMN role_id DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE chats ALTER COLUMN type DROP NOT NULL")
    op.execute("ALTER TABLE messages ALTER COLUMN created_at DROP NOT NULL")
