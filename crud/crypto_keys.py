import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from models.Crypto_keys import CryptoKeys
from schemas import UploadCryptKeys


async def add_crypto_keys(db: AsyncSession, keys: UploadCryptKeys, user_id: str):
    try:
        # Валидация UUID
        user_id = uuid.UUID(user_id)

        # Валидация ключей
        if not keys.public_key or not keys.private_key:
            raise HTTPException(status_code=400, detail="Public or private key cannot be empty")

        # Проверка существования ключей для пользователя
        existing_keys = (await db.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))).scalars().first()
        if existing_keys:
            raise HTTPException(status_code=400, detail="Keys for this user already exist")

        # Создание новой записи
        key_pair = CryptoKeys(
            user_id=user_id,
            public_key=keys.public_key,
            private_key=keys.private_key,
        )

        db.add(key_pair)
        await db.commit()
        await db.refresh(key_pair)
        return key_pair

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def get_user_crypto_keys(db: AsyncSession, user_id: uuid.UUID) -> CryptoKeys:
    try:
        user_keys = await db.execute(select(CryptoKeys).where(CryptoKeys.user_id == user_id))
        result = user_keys.scalars().first()

        if result is None:
            raise HTTPException(status_code=404, detail="Crypto keys not found for this user")

        return result

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except SQLAlchemyError as e:
        return e
        raise HTTPException(status_code=502, detail=f"Database error: {str(e)}")
    except Exception as e:
        return e
        return HTTPException(status_code=504, detail=f"Unexpected error: {str(e)}")