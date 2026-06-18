import base64
import os
import uuid

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.logger import logger
from models.crypto_key import CryptoKeys
from schemas.auth import StoredCryptKeys

KDF_ITERATIONS = 200_000
KDF_KEY_BYTES = 32
KDF_SALT_BYTES = 16
NONCE_BYTES = 12


def _derive_storage_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KDF_KEY_BYTES,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_private_key_for_storage(private_key: str, password: str) -> StoredCryptKeys:
    salt = os.urandom(KDF_SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    wrapping_key = _derive_storage_key(password=password, salt=salt)
    encrypted_private_key = AESGCM(wrapping_key).encrypt(
        nonce,
        private_key.encode("utf-8"),
        None,
    )
    return StoredCryptKeys(
        public_key="",
        encrypted_private_key=base64.b64encode(encrypted_private_key).decode("utf-8"),
        kdf_salt=base64.b64encode(salt).decode("utf-8"),
        encryption_nonce=base64.b64encode(nonce).decode("utf-8"),
    )


def generate_rsa_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.PKCS1,
    ).decode()
    return public_pem, private_pem


async def create_crypto_keys(
    session: AsyncSession,
    keys: StoredCryptKeys,
    user_id: str | uuid.UUID,
) -> CryptoKeys:
    try:
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        if (
            not keys.public_key
            or not keys.encrypted_private_key
            or not keys.kdf_salt
            or not keys.encryption_nonce
        ):
            raise HTTPException(status_code=400, detail="Incomplete crypto keys payload")

        existing_keys = (
            await session.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))
        ).scalars().first()
        if existing_keys is not None:
            raise HTTPException(status_code=400, detail="Keys for this user already exist")

        key_pair = CryptoKeys(
            user_id=user_id,
            public_key=keys.public_key,
            encrypted_private_key=keys.encrypted_private_key,
            kdf_salt=keys.kdf_salt,
            encryption_nonce=keys.encryption_nonce,
        )
        session.add(key_pair)
        await session.flush()
        await session.refresh(key_pair)
        return key_pair
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from exc


async def upsert_crypto_keys(
    session: AsyncSession,
    keys: StoredCryptKeys,
    user_id: str | uuid.UUID,
) -> CryptoKeys:
    try:
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        existing_keys = (
            await session.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))
        ).scalars().first()
        if existing_keys is None:
            return await create_crypto_keys(session=session, keys=keys, user_id=user_id)

        existing_keys.public_key = keys.public_key
        existing_keys.encrypted_private_key = keys.encrypted_private_key
        existing_keys.kdf_salt = keys.kdf_salt
        existing_keys.encryption_nonce = keys.encryption_nonce
        await session.flush()
        await session.refresh(existing_keys)
        return existing_keys
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from exc


async def get_user_crypto_keys(session: AsyncSession, user_id: uuid.UUID) -> CryptoKeys:
    try:
        user_keys = await session.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))
        result = user_keys.scalars().first()
        if result is None:
            raise HTTPException(status_code=404, detail="Crypto keys not found for this user")
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from exc
    except SQLAlchemyError as exc:
        logger.error("Database error: %s", str(exc))
        raise HTTPException(status_code=500, detail="Database error occurred") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}") from exc


async def create_seed_crypto_keys(
    session: AsyncSession,
    user_id: uuid.UUID,
    password: str,
) -> CryptoKeys:
    public_key, private_key = generate_rsa_key_pair()
    encrypted_keys = encrypt_private_key_for_storage(private_key=private_key, password=password)
    encrypted_keys.public_key = public_key
    return await create_crypto_keys(session=session, keys=encrypted_keys, user_id=user_id)
