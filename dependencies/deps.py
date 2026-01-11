from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from cache.redis_client import redis_client
from config.db import session_helper
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

UserTokenDep = Annotated[dict[str, str], Depends(verify_user_middleware)]

RedisDep = Annotated[EmailVerificationRedisService, Depends(get_email_verification_service)]

def get_email_service(
    redis: RedisDep,
) -> Email:
    return Email(redis)

EmailDep = Annotated[Email, Depends(get_email_service)]
