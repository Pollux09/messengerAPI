from fastapi import HTTPException
from redis.asyncio import Redis
from starlette import status
from config.logger import logger


class EmailVerificationRedisService:
    """
    Utility class for working with email verification cache
    """
    def __init__(
        self,
        redis: Redis,
        expire_seconds: int = 180,
        max_tries_count: int = 3,
    ) -> None:
        self.redis = redis
        self.expire_seconds = expire_seconds
        self.max_tries_count = max_tries_count


    async def add_verify_code(self, email: str, code: str) -> str:
        try:
            await self.redis.hset(email, mapping={
                "call_count": 0,
                "code": code
            })
            await self.redis.expire(email, self.expire_seconds)
            return code
        except Exception as e:
            logger.error('add verify code error: ' + str(e))
            raise HTTPException(detail='Internal Error', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    async def get_verify_code(self, email: str) -> dict[str, int] | None:
        try:
            data = await self.redis.hgetall(email)
            if not data:
                return None

            call_count = int(data.get("call_count", 0))
            code = int(data.get("code", 0))

            return {
                'call_count': call_count,
                'code': code
            }
        except Exception as e:
            logger.error('add verify code error: ' + str(e))
            raise HTTPException(detail='Internal Error', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    async def update_call_count(self, email: str) -> None:
        try:
            await self.redis.hincrby(email, "call_count", 1)
            await self.redis.expire(email, self.expire_seconds)
        except Exception as e:
            raise HTTPException(detail='Internal Error', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
