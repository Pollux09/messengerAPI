import smtplib
from email.mime.multipart import MIMEMultipart
from random import randint
from fastapi import HTTPException
from email.mime.text import MIMEText
import logging
from starlette import status
from config.settings import settings
from utils.mail.templates.confirm_email import get_confirm_email_html
from utils.redis.util import EmailVerificationRedisService


async def generate_code() -> int:
    return randint(100000, 999999)

class Email:
    def __init__(self, redis: EmailVerificationRedisService) -> None:
        self.redis = redis


    async def generate_email(self, to_send_email_address: str, email_code: str):
        msg = MIMEMultipart()
        msg['Subject'] = 'Messenger'
        msg['From'] = settings.APP_NAME
        msg['To'] = to_send_email_address

        html = get_confirm_email_html(email_code=email_code)
        msg.attach(MIMEText(html, 'html'))
        return msg


    async def send_email(self, to_send_email: str):
        to_send_email = to_send_email.lower()
        server = None

        try:
            verify_code = await generate_code()

            server = smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=10)
            server.starttls()
            server.login(settings.email_from, settings.email_password)
            message = await self.generate_email(to_send_email, str(verify_code))
            server.send_message(message)

            await self.redis.add_verify_code(email=to_send_email, code=str(verify_code))
            return True
        finally:
            server.quit()


    async def verify_email_code(self, user_email: str, user_code) -> bool:
        user_email = user_email.lower()

        try:
            verify_code_data = await self.redis.get_verify_code(email=user_email)

            if not verify_code_data:
                raise HTTPException(detail='Has no verify code for this email', status_code=status.HTTP_400_BAD_REQUEST)

            call_count = verify_code_data.get('call_count')
            code = verify_code_data.get('code')

            if call_count > 2:
                raise HTTPException(detail='Code entry limit exceeded', status_code=status.HTTP_429_TOO_MANY_REQUESTS)

            await self.redis.update_call_count(email=user_email)
            return code == int(user_code)
        except Exception as e:
            logging.error(f"Redis error during verification: {e}")
            raise HTTPException(detail='Internal error', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
