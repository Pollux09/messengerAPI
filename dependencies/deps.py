from typing import Annotated, Any

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from cache.redis_client import redis_client
from config.db import session_helper
from crud.users import ensure_user_is_approved, get_user_by_id
from utils.jwt_util import verify_user_middleware
from utils.mail.mail import Email
from utils.redis.util import EmailVerificationRedisService

def get_redis():
    return redis_client

def get_email_verification_service(
    redis = Depends(get_redis),
) -> EmailVerificationRedisService:
    return EmailVerificationRedisService(redis)

SessionDep = Annotated[AsyncSession, Depends(session_helper.session_getter)]

DecodedUserTokenDep = Annotated[dict[str, Any], Depends(verify_user_middleware)]

RedisDep = Annotated[EmailVerificationRedisService, Depends(get_email_verification_service)]

def get_email_service(
    redis: RedisDep,
) -> Email:
    return Email(redis)

EmailDep = Annotated[Email, Depends(get_email_service)]


async def get_current_approved_user(
    session: SessionDep,
    decoded_access_token: DecodedUserTokenDep,
):
    user = await get_user_by_id(session=session, user_id=decoded_access_token["user_id"])
    return await ensure_user_is_approved(user)


CurrentUserDep = Annotated[object, Depends(get_current_approved_user)]


async def get_approved_user_token(
    _current_user: CurrentUserDep,
    decoded_access_token: DecodedUserTokenDep,
) -> dict[str, Any]:
    return decoded_access_token


UserTokenDep = Annotated[dict[str, Any], Depends(get_approved_user_token)]


async def get_admin_user(
    current_user: CurrentUserDep,
):
    if current_user.role is None or not current_user.role.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
AdminUserDep = Annotated[object, Depends(get_admin_user)]
