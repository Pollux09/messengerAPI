"""encrypt private keys for client-side decryption

Revision ID: e7b1e2c4d001
Revises: c3a4a9c1d221
Create Date: 2026-06-17 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b1e2c4d001"
down_revision: Union[str, None] = "c3a4a9c1d221"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS crypto_keys (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            public_key VARCHAR NOT NULL,
            encrypted_private_key VARCHAR NOT NULL DEFAULT '',
            kdf_salt VARCHAR NOT NULL DEFAULT '',
            encryption_nonce VARCHAR NOT NULL DEFAULT ''
        )
        """
    )
    op.execute(
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS encrypted_private_key VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS kdf_salt VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS encryption_nonce VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'crypto_keys' AND column_name = 'private_key'
            ) THEN
                UPDATE crypto_keys
                SET encrypted_private_key = private_key
                WHERE private_key IS NOT NULL;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE crypto_keys DROP COLUMN IF EXISTS private_key")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE crypto_keys ADD COLUMN IF NOT EXISTS private_key VARCHAR NOT NULL DEFAULT ''"
    )
    op.execute(
        """
        UPDATE crypto_keys
        SET private_key = encrypted_private_key
        """
    )
    op.execute("ALTER TABLE crypto_keys DROP COLUMN IF EXISTS encryption_nonce")
    op.execute("ALTER TABLE crypto_keys DROP COLUMN IF EXISTS kdf_salt")
    op.execute("ALTER TABLE crypto_keys DROP COLUMN IF EXISTS encrypted_private_key")
