import datetime
import uuid
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from config.logger import logger
from config.settings import settings
from models.user import User

class JwtUtil:
    """
    Utility class for working with JWT tokens
    """
    def __init__(
        self,
        secret_key: str,
        algorithm: str,
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    async def create_jwt_tokens(self, user: User) -> tuple[str, str]:
        try:
            access_token_data = {
                "user_id": str(user.id),
                "username": user.username,
                "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(hours=12),
                "type": "access",
            }
            refresh_token_data = {
                "user_id": str(user.id),
                "username": user.username,
                "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=30),
                "type": "refresh",
            }

            access_token = jwt.encode(access_token_data, self.secret_key, algorithm=self.algorithm)
            refresh_token = jwt.encode(refresh_token_data, self.secret_key, algorithm=self.algorithm)

            return access_token, refresh_token
        except Exception as e:
            logger.error("create jwt token error: %s", str(e))
            raise HTTPException(status_code=500, detail="Failed to create token")


    async def decode_jwt_token(
        self,
        token: str,
        required_type: str | None = None,
    ) -> dict[str, str | uuid.UUID]:
        try:
            decoded_token = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            token_type = decoded_token.get("type")
            if required_type is not None and token_type != required_type:
                raise HTTPException(status_code=401, detail="Invalid token type")
            decoded_token["user_id"] = uuid.UUID(decoded_token["user_id"])
            return decoded_token
        except HTTPException:
            raise
        except ExpiredSignatureError as e:
            logger.error("jwt token expired: %s", str(e))
            raise HTTPException(status_code=401, detail="Token expired")
        except (InvalidTokenError, ValueError) as e:
            logger.error("decode jwt token error: %s", str(e))
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error("unexpected jwt token error: %s", str(e))
            raise HTTPException(status_code=500, detail="Token verification failed")
    
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
async def verify_user_middleware(token: str = Depends(oauth2_scheme)) -> dict[str, str]:
    return await jwt_util.decode_jwt_token(token=token, required_type="access")


jwt_util = JwtUtil(
    secret_key=settings.JWT_SECRET_TOKEN,
    algorithm=settings.JWT_ALGORITHM
)


jwtUtil = jwt_util
