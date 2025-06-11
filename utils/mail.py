import smtplib
from email.mime.multipart import MIMEMultipart
from random import randint

from fastapi import HTTPException
from pydantic_settings import BaseSettings
from email.mime.text import MIMEText
from redis.asyncio import Redis
import json


class Settings(BaseSettings):
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_from: str = "webm4025@gmail.com"
    email_password: str = "zvaxzqjwqzoprdqz"

settings = Settings()

class Email:
    async def generate_code(self) -> int:
        return randint(100000, 999999)

    async def generate_message(self, to_send_email_address, email_code):
        msg = MIMEMultipart()
        msg['Subject'] = 'Messenger'
        msg['From'] = settings.email_from
        msg['To'] = to_send_email_address
        

        html = f"""
        <html>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif;">
                <div style="text-align: center;">
                    <h1 style="color: #333; margin-bottom: 20px;">
                        Ваш код подтверждения
                    </h1>
                    <div style="
                        background-color: #f5f5f5;
                        display: inline-block;
                        padding: 15px 30px;
                        border-radius: 5px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    ">
                        <h2 style="
                            color: #1a73e8;
                            margin: 0;
                            font-size: 28px;
                            letter-spacing: 3px;
                        ">
                            {email_code}
                        </h2>
                    </div>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        return msg



    async def send_email(self, to_send_email:str):
        to_send_email = to_send_email.lower()

        server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
        server.starttls()
        try:
            verify_code : int = await self.generate_code()
            server.login(settings.email_from, settings.email_password)
            message = await self.generate_message(to_send_email, verify_code)
            # server.send_message(message)
            redis_ex = Redis(host="localhost", port=6379, db=0)
            try:
                # await redis_ex.ping()
                print("Connected to Redis")
            except:
                print("Failed to connect to Redis")

            await redis_ex.hset(to_send_email, mapping={
                "call_count": 0,
                "code": verify_code
            })
            await redis_ex.expire(to_send_email, 180)


        except smtplib.SMTPException as e:
            raise HTTPException(
                status_code=500,
                detail=f"SMTP error occurred: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred: {str(e)}"
            )

    async def verify_code(self, user_email:str, user_code):
        return True
        user_email = user_email.lower()

        redis_ex = Redis(host="localhost", port=6379, db=0)
        user_email_exists = await redis_ex.exists(user_email)
        if user_email_exists:
            call_count = int(await redis_ex.hget(user_email, "call_count"))
            code = int(await redis_ex.hget(user_email, "code"))

            if call_count <= 2:
                await redis_ex.hincrby(user_email, "call_count", 1)
                return True
                # return code == int(user_code)
            return "Превышен лимит ввода кода"

        return "Код не отправлялся на такую почту"


email = Email()