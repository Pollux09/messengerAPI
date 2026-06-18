import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from psycopg2 import DatabaseError
from config.settings import settings
from crud.crypto_keys import create_crypto_keys, create_seed_crypto_keys, get_user_crypto_keys
from models.role import Role
from models.user import User
from passlib.context import CryptContext
from schemas.auth import LoginData, SignUpRequest
from schemas.chat import UpdateUserAvatar
from schemas.user import (
    RegistrationDecision,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UpdateProfile,
    UpdateUsername,
    UserResponse,
)
from websocket_managers.chats_manager import chats_manager

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")
REGISTRATION_PENDING = "pending"
REGISTRATION_APPROVED = "approved"
REGISTRATION_REJECTED = "rejected"
DEFAULT_ADMIN_ROLE_TITLE = "Админ"
DEFAULT_USER_ROLE_TITLE = "Пользователь"

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_username(username: str) -> str:
    cleaned = username.strip().lstrip("@").lower()
    if not USERNAME_RE.fullmatch(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Username должен содержать 3-32 латинские буквы, цифры или символ подчеркивания",
        )
    return f"@{cleaned}"


def is_protected_admin(user: User) -> bool:
    return user.email.lower() == settings.ADMIN_EMAIL.lower()


def user_is_admin(user: User) -> bool:
    return bool(user.role and user.role.is_admin)


async def build_user_response(session: AsyncSession, user: User) -> UserResponse:
    try:
        keys = await get_user_crypto_keys(session=session, user_id=user.id)
        public_key = keys.public_key
    except HTTPException:
        public_key = ""
    return UserResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        email=user.email,
        phone_number=user.phone_number,
        avatar_photo=user.avatar_photo,
        user_public_key=public_key,
        is_admin=user_is_admin(user),
        is_online=chats_manager.is_online(str(user.id)),
        registration_status=user.registration_status,
        rejection_reason=user.rejection_reason,
        role_id=user.role_id,
        role_title=user.role.title if user.role else None,
        last_seen_at=user.last_seen_at,
    )


async def get_user(session: AsyncSession, user_id: str | uuid.UUID) -> UserResponse:
    user = await get_user_by_id(session, user_id)
    return await build_user_response(session, user)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(func.lower(User.email) == email.lower())
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def delete_rejected_registration_by_email(
    session: AsyncSession,
    email: str,
) -> bool:
    user = await get_user_by_email(session, email)
    if user is None or user.registration_status != REGISTRATION_REJECTED:
        return False

    await session.delete(user)
    await session.flush()
    return True


async def delete_unapproved_user(session: AsyncSession, user: User) -> None:
    if user.registration_status == REGISTRATION_APPROVED:
        raise HTTPException(status_code=400, detail="Approved user cannot be deleted by this operation")

    await session.delete(user)
    await session.commit()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = normalize_username(username)
    stmt = select(User).options(selectinload(User.role)).where(User.username == normalized)
    result = await session.execute(stmt)
    return result.scalars().first()


async def ensure_username_available(
    session: AsyncSession,
    username: str,
    exclude_user_id: uuid.UUID | None = None,
) -> str:
    normalized = normalize_username(username)
    stmt = select(User).where(User.username == normalized)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Этот username уже занят")
    return normalized


async def create_user(session: AsyncSession, user: SignUpRequest) -> User:
    await delete_rejected_registration_by_email(session, user.email)
    hashed_password = pwd_context.hash(user.password)
    normalized_username = await ensure_username_available(session, user.username)
    default_role = await get_or_create_default_role(session, DEFAULT_USER_ROLE_TITLE, is_admin=False)
    session_user = User(
        email=user.email.lower(),
        username=normalized_username,
        nickname=user.nickname.strip(),
        hashed_password=hashed_password,
        registration_status=REGISTRATION_PENDING,
        role_id=default_role.id,
    )
    session.add(session_user)
    try:
        await session.flush()
        await create_crypto_keys(session, user.crypt_keys, session_user.id)
        await session.commit()
        await session.refresh(session_user, ["role"])
    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким email или username уже существует",
        ) from exc
    return session_user


async def create_seed_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    username: str,
    is_admin: bool = False,
) -> User:
    existing = await get_user_by_email(session, email)
    if existing:
        try:
            await get_user_crypto_keys(session, existing.id)
        except HTTPException:
            await create_seed_crypto_keys(session, existing.id, password=password)
            await session.commit()
            await session.refresh(existing, ["role"])
        return existing

    normalized_username = await ensure_username_available(session, username)
    admin_role = await get_or_create_default_role(session, DEFAULT_ADMIN_ROLE_TITLE, is_admin=True)
    user_role = await get_or_create_default_role(session, DEFAULT_USER_ROLE_TITLE, is_admin=False)
    role = admin_role if is_admin else user_role
    user = User(
        email=email.lower(),
        username=normalized_username,
        nickname=username.strip().lstrip("@"),
        hashed_password=pwd_context.hash(password),
        role_id=role.id,
        registration_status=REGISTRATION_APPROVED,
    )
    session.add(user)
    await session.flush()
    await create_seed_crypto_keys(session, user.id, password=password)
    await session.commit()
    await session.refresh(user, ["role"])
    return user


async def update_username(session: AsyncSession, current_user_id: uuid.UUID, data: UpdateUsername) -> UserResponse:
    user = await get_user_by_id(session, current_user_id)
    user.username = await ensure_username_available(session, data.username, exclude_user_id=user.id)
    await session.commit()
    await session.refresh(user)
    return await build_user_response(session, user)


async def update_profile(
    session: AsyncSession,
    current_user_id: uuid.UUID,
    data: UpdateProfile,
) -> UserResponse:
    user = await get_user_by_id(session, current_user_id)
    user.nickname = data.nickname.strip()
    user.phone_number = data.phone_number.strip() if data.phone_number else None
    await session.commit()
    await session.refresh(user)
    return await build_user_response(session, user)


async def login_user(session: AsyncSession, login_data: LoginData) -> User:
    stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(func.lower(User.email) == login_data.email.lower())
    )
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь с таким email не найден")

    if not pwd_context.verify(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный пароль")

    if user.registration_status == REGISTRATION_PENDING:
        raise HTTPException(
            status_code=403,
            detail="Регистрация подтверждена по почте, но еще ожидает одобрения администратора",
        )
    if user.registration_status == REGISTRATION_REJECTED:
        raise HTTPException(
            status_code=403,
            detail="Регистрация была отклонена администратором. Подробности отправлены на вашу почту",
        )
    return user


async def ensure_user_is_approved(user: User) -> User:
    if user.registration_status == REGISTRATION_PENDING:
        raise HTTPException(
            status_code=403,
            detail="Ваш аккаунт ожидает подтверждения администратора",
        )
    if user.registration_status == REGISTRATION_REJECTED:
        raise HTTPException(
            status_code=403,
            detail="Ваш аккаунт отклонен администратором. Подробности отправлены на почту",
        )
    return user


async def update_user_last_seen(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    seen_at: datetime | None = None,
) -> None:
    user = await get_user_by_id(session, user_id)
    user.last_seen_at = seen_at or datetime.now(timezone.utc)
    await session.commit()


async def check_user_exists(session: AsyncSession, email: str) -> bool:
    await delete_rejected_registration_by_email(session, email)
    user = await get_user_by_email(session, email)
    return user is not None


async def get_user_by_id(session: AsyncSession, user_id: str | uuid.UUID) -> User:
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid user ID format") from exc

    stmt = select(User).options(selectinload(User.role)).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


async def get_users_list(
    session: AsyncSession,
    *,
    current_user_id: uuid.UUID | None = None,
    admins_only: bool = False,
    exclude_current_user: bool = True,
) -> list[UserResponse]:
    stmt = select(User).order_by(func.lower(User.nickname), func.lower(User.username))
    stmt = stmt.options(selectinload(User.role))
    if admins_only:
        stmt = stmt.join(Role, User.role_id == Role.id).where(Role.is_admin.is_(True))
    stmt = stmt.where(User.registration_status == REGISTRATION_APPROVED)
    if current_user_id is not None and exclude_current_user:
        stmt = stmt.where(User.id != current_user_id)
    result = await session.execute(stmt)
    users = result.scalars().all()
    return [await build_user_response(session, user) for user in users]


async def search_users(
    session: AsyncSession,
    query: str,
    current_user_id: uuid.UUID | None = None,
) -> list[UserResponse]:
    normalized = query.strip().lstrip("@").lower()
    stmt = select(User).where(
        func.lower(User.username).ilike(f"%{normalized}%")
        | func.lower(User.nickname).ilike(f"%{normalized}%")
    )
    stmt = stmt.options(selectinload(User.role))
    stmt = stmt.where(User.registration_status == REGISTRATION_APPROVED)
    stmt = stmt.order_by(func.lower(User.nickname), func.lower(User.username))
    result = await session.execute(stmt)
    users = result.scalars().all()
    final_result_list = []

    for user in users:
        try:
            final_result_list.append(await build_user_response(session, user))
        except HTTPException:
            continue
    return final_result_list


async def add_user_avatar(session: AsyncSession, update_avatar: UpdateUserAvatar):
    if not isinstance(update_avatar.user_id, (uuid.UUID, str)):
        raise HTTPException(status_code=400, detail="User ID must be a UUID or a string")

    try:
        user_id = (
            update_avatar.user_id
            if isinstance(update_avatar.user_id, uuid.UUID)
            else uuid.UUID(update_avatar.user_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user ID format") from exc

    if not update_avatar.photo_data:
        raise HTTPException(status_code=400, detail="Photo data cannot be empty")

    try:
        async with session.begin():
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user.avatar_photo = update_avatar.photo_data
        return user
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail="Database error occurred") from exc


async def check_user_exists_by_id(session: AsyncSession, user_id: str | uuid.UUID):
    await get_user_by_id(session, user_id)
    return True


# Temporary aliases for modules that still use the previous naming.
getUserById = get_user_by_id
checkUserExists = check_user_exists_by_id


async def get_or_create_default_role(
    session: AsyncSession,
    title: str,
    *,
    is_admin: bool,
) -> Role:
    stmt = select(Role).where(func.lower(Role.title) == title.lower())
    role = (await session.execute(stmt)).scalars().first()
    if role is not None:
        if role.is_default is False:
            role.is_default = True
            await session.commit()
            await session.refresh(role)
        return role

    role = Role(title=title, is_admin=is_admin, is_default=True)
    session.add(role)
    await session.flush()
    await session.commit()
    await session.refresh(role)
    return role


async def get_all_roles(session: AsyncSession) -> list[RoleResponse]:
    result = await session.execute(select(Role).order_by(Role.is_admin.desc(), func.lower(Role.title)))
    roles = result.scalars().all()
    return [
        RoleResponse(
            id=role.id,
            title=role.title,
            is_admin=role.is_admin,
            is_default=role.is_default,
        )
        for role in roles
    ]


async def create_role(session: AsyncSession, data: RoleCreate) -> RoleResponse:
    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Role title cannot be empty")

    existing = (
        await session.execute(select(Role).where(func.lower(Role.title) == title.lower()))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Role with this title already exists")

    role = Role(title=title, is_admin=data.is_admin, is_default=False)
    session.add(role)
    await session.flush()
    await session.commit()
    await session.refresh(role)
    return RoleResponse(
        id=role.id,
        title=role.title,
        is_admin=role.is_admin,
        is_default=role.is_default,
    )


async def get_pending_users(session: AsyncSession) -> list[UserResponse]:
    result = await session.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.registration_status == REGISTRATION_PENDING)
        .order_by(func.lower(User.nickname), func.lower(User.username))
    )
    users = result.scalars().all()
    return [await build_user_response(session, user) for user in users]


async def update_user_registration_status(
    session: AsyncSession,
    data: RegistrationDecision,
    *,
    new_status: str,
) -> User:
    user = await get_user_by_id(session, data.user_id)
    if user.registration_status != REGISTRATION_PENDING:
        raise HTTPException(status_code=409, detail="This registration request is already processed")

    if user.role_id is None:
        default_role = await get_or_create_default_role(
            session,
            DEFAULT_USER_ROLE_TITLE,
            is_admin=False,
        )
        user.role_id = default_role.id

    user.registration_status = new_status
    user.rejection_reason = None
    if new_status == REGISTRATION_REJECTED:
        rejection_reason = (data.rejection_reason or "").strip()
        user.rejection_reason = rejection_reason or None
    await session.commit()
    await session.refresh(user, ["role"])
    return user


async def update_user_role(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: RoleUpdate,
) -> UserResponse:
    user = await get_user_by_id(session, user_id)
    role = (await session.execute(select(Role).where(Role.id == data.role_id))).scalars().first()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if is_protected_admin(user) and not role.is_admin:
        raise HTTPException(
            status_code=409,
            detail="Нельзя снять права администратора у главного системного администратора",
        )

    user.role_id = role.id
    await session.commit()
    await session.refresh(user, ["role"])
    return await build_user_response(session, user)
