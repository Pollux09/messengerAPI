import datetime
import os
from fastapi import HTTPException
import jwt
from dotenv import load_dotenv

from models.User import User

load_dotenv()

class JwtUtil:
    secret_key = os.getenv("JWT_SECRET_TOKEN")
    alhoritm = os.getenv("JWT_ALGORITM")
    
    async def createJwtTokens(self, user: User):
        access_token_data = {
            "user_id": str(user.id),
            "username": user.username,
            "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds=15),
            "type": "access",
        }
        refresh_token_data = {
            "user_id": str(user.id),
            "username": user.username,
            "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=30),
            "type": "refresh",
        }

        access_token = jwt.encode(access_token_data, self.secret_key, algorithm=self.alhoritm)
        refresh_token = jwt.encode(refresh_token_data, self.secret_key, algorithm=self.alhoritm)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    
    async def decodeJwtToken(self, token: str):
        try:
            decoded_token = jwt.decode(token, self.secret_key, algorithms=self.alhoritm)
            return decoded_token
        except Exception as e:
            print("error is: ")
            print(e)
            return False
    
jwtUtil = JwtUtil()
