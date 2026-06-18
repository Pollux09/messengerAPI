import smtplib
from email.mime.multipart import MIMEMultipart
from random import randint
from fastapi import HTTPException
from email.mime.text import MIMEText
from starlette import status
from config.logger import logger
from config.settings import settings
from utils.mail.templates.confirm_email import get_confirm_email_html
from utils.mail.templates.registration_decision import get_registration_decision_html
from utils.mail.templates.registration_pending import get_registration_pending_html
from utils.redis.util import EmailVerificationRedisService


async def generate_code() -> int:
    return randint(100000, 999999)

class Email:
    def __init__(self, redis: EmailVerificationRedisService) -> None:
        self.redis = redis


    async def generate_email(self, to_send_email_address: str, email_code: str):
        msg = MIMEMultipart()
        msg['Subject'] = f'{settings.APP_NAME}: код подтверждения'
        msg['From'] = settings.SMTP_FROM or settings.SMTP_USERNAME or "no-reply@messenger.local"
        msg['To'] = to_send_email_address

        html = get_confirm_email_html(email_code=email_code)
        msg.attach(MIMEText(html, 'html'))
        return msg


    async def generate_custom_email(
        self,
        to_send_email_address: str,
        *,
        subject: str,
        html: str,
    ):
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_FROM or settings.SMTP_USERNAME or "no-reply@messenger.local"
        msg['To'] = to_send_email_address
        msg.attach(MIMEText(html, 'html'))
        return msg


    async def send_email(self, to_send_email: str):
        to_send_email = to_send_email.lower()
        server = None

        try:
            verify_code = await generate_code()

            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
            else:
                server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
                server.ehlo()

            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                if settings.SMTP_PORT != 465 and settings.SMTP_USE_TLS and server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            message = await self.generate_email(to_send_email, str(verify_code))
            server.send_message(message)

            await self.redis.add_verify_code(email=to_send_email, code=str(verify_code))
            return True
        except smtplib.SMTPException as e:
            logger.error("SMTP error during email sending: %s", str(e))
            raise HTTPException(
                detail="Failed to send verification code",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected email sending error: %s", str(e))
            raise HTTPException(
                detail="Internal error while sending email",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            if server is not None:
                server.quit()


    async def send_registration_pending_email(self, to_send_email: str, nickname: str):
        html = get_registration_pending_html(nickname)
        await self._send_plain_message(
            to_send_email,
            subject=f"{settings.APP_NAME}: заявка принята",
            html=html,
        )


    async def send_registration_decision_email(
        self,
        to_send_email: str,
        nickname: str,
        approved: bool,
        rejection_reason: str | None = None,
    ):
        html = get_registration_decision_html(
            nickname,
            approved=approved,
            rejection_reason=rejection_reason,
        )
        subject = (
            f"{settings.APP_NAME}: регистрация одобрена"
            if approved
            else f"{settings.APP_NAME}: регистрация отклонена"
        )
        await self._send_plain_message(
            to_send_email,
            subject=subject,
            html=html,
        )


    async def _send_plain_message(self, to_send_email: str, *, subject: str, html: str):
        to_send_email = to_send_email.lower()
        server = None
        try:
            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
            else:
                server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
                server.ehlo()

            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                if settings.SMTP_PORT != 465 and settings.SMTP_USE_TLS and server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

            message = await self.generate_custom_email(
                to_send_email,
                subject=subject,
                html=html,
            )
            server.send_message(message)
        except smtplib.SMTPException as e:
            logger.error("SMTP error during email sending: %s", str(e))
            raise HTTPException(
                detail="Failed to send email",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected email sending error: %s", str(e))
            raise HTTPException(
                detail="Internal error while sending email",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            if server is not None:
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
        except HTTPException:
            raise
        except ValueError as e:
            logger.error("Invalid verification code format: %s", str(e))
            raise HTTPException(
                detail="Verification code must be numeric",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error("Redis error during verification: %s", str(e))
            raise HTTPException(detail='Internal error', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
