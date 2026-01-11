import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from config.logger import logger
from models.CryptoKey import CryptoKeys
from schemas.auth import UploadCryptKeys


async def add_crypto_keys(session: AsyncSession, keys: UploadCryptKeys, user_id: str) -> CryptoKeys:
    try:
        user_id = uuid.UUID(user_id)

        # keys validation
        if not keys.public_key or not keys.private_key:
            raise HTTPException(status_code=400, detail="Public or private key cannot be empty")

        # check keys don't exist
        existing_keys = (await session.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))).scalars().first()
        if existing_keys:
            raise HTTPException(status_code=400, detail="Keys for this user already exist")

        # create keys
        key_pair = CryptoKeys(
            user_id=user_id,
            public_key=keys.public_key,
            private_key=keys.private_key,
        )

        session.add(key_pair)
        await session.commit()
        await session.refresh(key_pair)
        return key_pair

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def get_user_crypto_keys(session: AsyncSession, user_id: uuid.UUID) -> CryptoKeys:
    try:
        user_keys = await session.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))
        result = user_keys.scalars().first()

        if result is None:
            raise HTTPException(status_code=404, detail="Crypto keys not found for this user")

        return result

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except SQLAlchemyError as e:
        logger.error("Database error: " + str(e))
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        return e
        return HTTPException(status_code=504, detail=f"Unexpected error: {str(e)}")