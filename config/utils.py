import asyncio
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import text
from config.logger import logger
from config.settings import settings


async def init_db() -> None:
    try:
        await wait_for_database()
        await run_migrations_async()
        await ensure_runtime_schema()
        await seed_default_users()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        if settings.ENVIRONMENT != "production":
            logger.warning("Continuing without migrations in development mode")
        else:
            raise


async def wait_for_database(retries: int = 10, delay: int = 3):
    from config.db import session_helper

    for i in range(retries):
        try:
            async with session_helper.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Database is ready")
                return
        except Exception as e:
            logger.warning(f"Database not ready (attempt {i + 1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)

    raise ConnectionError(f"Database not available after {retries} attempts")


async def run_migrations_async():
    try:
        logger.info("Starting migrations...")
        project_dir = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(project_dir),
            env={**os.environ, "PYTHONPATH": str(project_dir)},
        )

        if result.stdout:
            logger.info(f"Migration stdout:\n{result.stdout}")

        if result.returncode != 0:
            logger.error(f"Migration stderr:\n{result.stderr}")
            logger.info("Trying to create tables directly...")
            await create_tables_directly()
            return

        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise


async def create_tables_directly():
    try:
        from config.db import Base, session_helper
        from models.chat import Chat
        from models.chat_member import ChatMember
        from models.crypto_key import CryptoKeys
        from models.message import Message
        from models.role import Role
        from models.user import User

        async with session_helper.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Tables created directly via SQLAlchemy")
    except Exception as e:
        logger.error(f"Error creating tables directly: {e}")
        raise


async def ensure_runtime_schema():
    from config.db import session_helper

    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR NOT NULL DEFAULT ''",
        "UPDATE users SET nickname = COALESCE(NULLIF(TRIM(BOTH '@' FROM username), ''), email) WHERE nickname = ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_status VARCHAR NOT NULL DEFAULT 'pending'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",
        """
        CREATE TABLE IF NOT EXISTS crypto_keys (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            public_key VARCHAR NOT NULL,
            encrypted_private_key VARCHAR NOT NULL,
            kdf_salt VARCHAR NOT NULL,
            encryption_nonce VARCHAR NOT NULL
        )
        """,
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS encrypted_private_key VARCHAR DEFAULT ''",
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS kdf_salt VARCHAR DEFAULT ''",
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS encryption_nonce VARCHAR DEFAULT ''",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'crypto_keys' AND column_name = 'private_key'
            ) THEN
                UPDATE crypto_keys
                SET encrypted_private_key = COALESCE(encrypted_private_key, private_key)
                WHERE encrypted_private_key IS NULL OR encrypted_private_key = '';
            END IF;
        END $$;
        """,
        """
        CREATE TABLE IF NOT EXISTS roles (
            id UUID PRIMARY KEY,
            title VARCHAR NOT NULL UNIQUE,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
            is_default BOOLEAN NOT NULL DEFAULT FALSE
        )
        """,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id UUID",
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_id_fkey",
        "ALTER TABLE users ADD CONSTRAINT users_role_id_fkey FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT",
        "ALTER TABLE chats ADD COLUMN IF NOT EXISTS title VARCHAR",
        "ALTER TABLE chats ADD COLUMN IF NOT EXISTS avatar_photo VARCHAR",
        "ALTER TABLE chats ADD COLUMN IF NOT EXISTS created_by UUID",
        "ALTER TABLE chats DROP CONSTRAINT IF EXISTS chats_created_by_fkey",
        "ALTER TABLE chats ADD CONSTRAINT chats_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL",
        "DROP TABLE IF EXISTS chat_types",
        """
        CREATE TABLE IF NOT EXISTS chat_members (
            chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (chat_id, user_id)
        )
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'chats' AND column_name = 'users_ids'
            ) THEN
                INSERT INTO chat_members (chat_id, user_id)
                SELECT chats.id, member_id
                FROM chats
                CROSS JOIN LATERAL unnest(chats.users_ids) AS member_id
                ON CONFLICT (chat_id, user_id) DO NOTHING;
            END IF;
        END $$;
        """,
        "ALTER TABLE chats DROP COLUMN IF EXISTS users_count",
        "ALTER TABLE chats DROP COLUMN IF EXISTS users_ids",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS encrypted_aes_key_sender TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS encrypted_aes_key_receiver TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS encrypted_keys JSON NOT NULL DEFAULT '{}'::json",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS iv TEXT NOT NULL DEFAULT ''",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_crypto_keys_user_id ON crypto_keys (user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_roles_title ON roles (title)",
        "CREATE INDEX IF NOT EXISTS ix_chat_members_user_id ON chat_members (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_messages_chat_id_created_at ON messages (chat_id, created_at)",
        "ALTER TABLE users ALTER COLUMN email SET NOT NULL",
        "ALTER TABLE users ALTER COLUMN username SET NOT NULL",
        "ALTER TABLE users ALTER COLUMN hashed_password SET NOT NULL",
        "ALTER TABLE chats ALTER COLUMN type SET NOT NULL",
        "ALTER TABLE messages ALTER COLUMN created_at SET NOT NULL",
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_registration_status",
        "ALTER TABLE users ADD CONSTRAINT ck_users_registration_status CHECK (registration_status IN ('pending', 'approved', 'rejected'))",
        "ALTER TABLE chats DROP CONSTRAINT IF EXISTS ck_chats_type",
        "ALTER TABLE chats ADD CONSTRAINT ck_chats_type CHECK (type IN ('private', 'group'))",
        "UPDATE users SET registration_status = 'approved' WHERE registration_status = 'pending' AND role_id IS NULL",
    ]

    async with session_helper.engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))

async def seed_default_users():
    from config.db import session_helper
    from crud.users import (
        DEFAULT_ADMIN_ROLE_TITLE,
        DEFAULT_USER_ROLE_TITLE,
        create_seed_user,
        get_or_create_default_role,
        get_user_by_email,
    )

    async with session_helper.session_factory() as session:
        admin_role = await get_or_create_default_role(
            session,
            DEFAULT_ADMIN_ROLE_TITLE,
            is_admin=True,
        )
        await get_or_create_default_role(
            session,
            DEFAULT_USER_ROLE_TITLE,
            is_admin=False,
        )
        user_role = await get_or_create_default_role(
            session,
            DEFAULT_USER_ROLE_TITLE,
            is_admin=False,
        )
        has_is_admin_column = bool(
            (
                await session.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'is_admin'
                        """
                    )
                )
            ).first()
        )
        legacy_users_query = (
            "SELECT id, email, is_admin FROM users WHERE role_id IS NULL"
            if has_is_admin_column
            else "SELECT id, email FROM users WHERE role_id IS NULL"
        )
        existing_users = (await session.execute(text(legacy_users_query))).all()
        if existing_users:
            for row in existing_users:
                is_admin_user = (
                    getattr(row, "is_admin", False)
                    or row.email.lower() == settings.ADMIN_EMAIL.lower()
                )
                role_id = admin_role.id if is_admin_user else user_role.id
                await session.execute(
                    text(
                        "UPDATE users SET role_id = CAST(:role_id AS UUID), registration_status = 'approved' "
                        "WHERE id = :user_id"
                    ),
                    {"role_id": role_id, "user_id": row.id},
                )
            await session.commit()
        admin = await get_user_by_email(session, settings.ADMIN_EMAIL)
        if admin is None:
            admin = await create_seed_user(
                session,
                email=settings.ADMIN_EMAIL,
                password=settings.ADMIN_PASSWORD,
                username=settings.ADMIN_USERNAME,
                is_admin=True,
            )
        elif admin.role_id != admin_role.id:
            admin.registration_status = "approved"
            admin.role_id = admin_role.id
            await session.commit()
            await session.refresh(admin, ["role"])
        if admin.role_id is None:
            admin.role_id = admin_role.id
            admin.registration_status = "approved"
            await session.commit()
            await session.refresh(admin, ["role"])
        await finalize_user_role_schema(session, admin_role.id, user_role.id, has_is_admin_column)
        logger.info("Default admin is ready")


async def finalize_user_role_schema(
    session,
    admin_role_id,
    user_role_id,
    has_is_admin_column: bool,
) -> None:
    if has_is_admin_column:
        await session.execute(
            text(
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

    await session.execute(
        text(
            """
            UPDATE users
            SET role_id = CAST(:user_role_id AS UUID)
            WHERE role_id IS NULL
            """
        ),
        {"user_role_id": user_role_id},
    )
    await session.execute(text("ALTER TABLE users ALTER COLUMN role_id SET NOT NULL"))
    await session.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_id_fkey"))
    await session.execute(
        text(
            """
            ALTER TABLE users
            ADD CONSTRAINT users_role_id_fkey
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
            """
        )
    )
    await session.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_admin"))
    await session.commit()
