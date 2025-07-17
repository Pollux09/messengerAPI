import uuid
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from psycopg2 import DatabaseError
from crud.crypto_keys import get_user_crypto_keys
from models.Crypto_keys import CryptoKeys
from models.User import User
from schemas import LoginData, UserCreate, UserResponse, UpdateUserAvatar
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_user(db: AsyncSession, user_id: str | uuid.UUID):
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this ID not found")
    keys = await get_user_crypto_keys(db=db, user_id=user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_photo=user.avatar_photo,
        user_public_key=keys.public_key,
    )


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    await db.flush()
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def login_user(db: AsyncSession, login_data: LoginData):
    stmt = select(User).where(User.email == login_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this email not found")

    if not pwd_context.verify(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    return user


async def check_user_exists(db: AsyncSession, email: str):
    try:
        user = await db.execute(select(User).where(User.email == email))
        result = user.scalars().first()

        if not result:
            return False
        return True
    except Exception as e:
        print(e)
        raise HTTPException(status_code=502, detail="Что-то пошло не так")


async def getUserById(db: AsyncSession, user_id: str | uuid.UUID):
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    return user


async def search_users_by_username(db: AsyncSession, username: str):
    try:
        stmt = select(User).where(func.lower(User.username).ilike(f"%{username.lower()}%"))
        result = await db.execute(stmt)
        users = result.scalars().all()
        final_result_list = []

        for user in users:
            keys: CryptoKeys = await get_user_crypto_keys(db=db, user_id=user.id)
            final_result_list.append(
                UserResponse(
                    id=user.id,
                    email=user.email,
                    username=user.username,
                    avatar_photo=user.avatar_photo,
                    user_public_key=keys.public_key
                )
            )
        return final_result_list
    except Exception as e:
        return e


async def add_user_avatar(db: AsyncSession, update_avatar: UpdateUserAvatar):
    # Проверка user_id
    if not isinstance(update_avatar.user_id, (uuid.UUID, str)):
        raise HTTPException(status_code=400, detail="User ID must be a UUID or a string")

    try:
        user_id = (
            update_avatar.user_id
            if isinstance(update_avatar.user_id, uuid.UUID)
            else uuid.UUID(update_avatar.user_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Проверка photo_data
    if not update_avatar.photo_data:
        raise HTTPException(status_code=400, detail="Photo data cannot be empty")

    try:
        async with db.begin():
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user.avatar_photo = update_avatar.photo_data
        return user
    except DatabaseError:
        raise HTTPException(status_code=500, detail="Database error occurred")


async def checkUserExists(db: AsyncSession, user_id: str | uuid.UUID):
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this ID not found")
    return True