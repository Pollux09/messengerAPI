import smtplib
from email.mime.multipart import MIMEMultipart
from random import randint

from fastapi import HTTPException
from pydantic_settings import BaseSettings
from email.mime.text import MIMEText
from redis.asyncio import Redis
import logging

class Settings(BaseSettings):
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_from: str = "webm4025@gmail.com"
    email_password: str = "zvaxzqjwqzoprdqz"

settings = Settings()

class Email:
    async def generate_code(self) -> int:
        return randint(100000, 999999)

    async def generate_message(self, to_send_email_address: str, email_code: int):
        msg = MIMEMultipart()
        msg['Subject'] = 'Messenger'
        msg['From'] = settings.email_from
        msg['To'] = to_send_email_address

        html = f"""
        <html>
            <body style="margin: 0; padding: 0; font-family: Arial, Helvetica, sans-serif; background-color: #f4f7fa;">
                <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <div style="background-color: #19A3FE; padding: 20px; text-align: center;">
                        <h1 style="color: #ffffff; font-size: 24px; margin: 10px 0 0; font-weight: 600; color: white">Подтверждение почты</h1>
                    </div>
                    <!-- Content -->
                    <div style="padding: 30px 20px; text-align: center;">
                        <h1 style="color: #333333; font-size: 22px; margin: 0 0 15px; font-weight: 600;">Ваш код подтверждения</h1>
                        <p style="color: #666666; font-size: 16px; line-height: 1.6; margin: 0 0 20px;">Спасибо за регистрацию в QuantumChat! Введите код ниже, чтобы подтвердить ваш адрес электронной почты:</p>
                        <div style="display: inline-block; background-color: #f0f8ff; padding: 15px 30px; border-radius: 6px; border: 1px solid #19A3FE; margin: 20px 0;">
                            <h2 style="color: #19A3FE; font-size: 28px; letter-spacing: 4px; margin: 0; font-weight: 600;">{email_code}</h2>
                        </div>
                        <p style="color: #666666; font-size: 16px; line-height: 1.6; margin: 0 0 20px;">Этот код действителен в течение <strong>3 минут</strong>.</p>
                        <p style="color: #888888; font-size: 14px; margin: 20px 0 0;">Если вы не регистрировались в QuantumChat, просто проигнорируйте это письмо.</p>
                    </div>
                    <!-- Footer -->
                    <div style="background-color: #f4f7fa; padding: 15px; text-align: center; font-size: 14px; color: #888888;">
                        <p style="margin: 0;">© 2025 QuantumChat. Все права защищены.</p>
                        <p style="margin: 5px 0;">
                            <a href="https://your-app-url.com/support" style="color: #19A3FE; text-decoration: none;">Связаться с поддержкой</a> | 
                            <a href="https://your-app-url.com/privacy" style="color: #19A3FE; text-decoration: none;">Политика конфиденциальности</a>
                        </p>
                    </div>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        return msg

    async def send_email(self, to_send_email: str):
        to_send_email = to_send_email.lower()
        server = None
        redis_ex = None

        try:
            verify_code = await self.generate_code()

            try:
                server = smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=10)
                server.starttls()
                server.login(settings.email_from, settings.email_password)
                message = await self.generate_message(to_send_email, verify_code)
                server.send_message(message)
                print("письмо успешно отправлено на указанный адрес")
            except Exception as smtp_err:
                print('ошибка отправки письма')
                raise HTTPException(
                    status_code=500,
                    detail=f"SMTP error: {str(smtp_err)}"
                )

            try:
                redis_ex = Redis(host="redis", port=6379, db=0)
                await redis_ex.hset(to_send_email, mapping={
                    "call_count": 0,
                    "code": verify_code
                })
                await redis_ex.expire(to_send_email, 180)
                print('code was added to redis: ' + str(verify_code))
                return True
            except Exception as redis_err:
                print("ошибка при добавлении кода в redis")
                raise HTTPException(detail="ошибка при добавлении кода в redis")
                logging.error(f"Redis error: {redis_err}")
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass
            if redis_ex:
                try:
                    await redis_ex.close()
                except Exception:
                    pass
        raise HTTPException(status_code=421, detail="Сервис недоступен, канал передачи закрывается. Возможная причина - перегрузка сервера или технические работы.")

    async def verify_code(self, user_email: str, user_code):
        user_email = user_email.lower()
        redis_ex = Redis(host="redis", port=6379, db=0)

        try:
            user_email_exists = await redis_ex.exists(user_email)
            if user_email_exists:
                call_count = int(await redis_ex.hget(user_email, "call_count") or 0)
                code = int(await redis_ex.hget(user_email, "code") or 0)

                if call_count <= 2:
                    await redis_ex.hincrby(user_email, "call_count", 1)
                    return code == int(user_code)
                return "Превышен лимит ввода кода"

            return "Код не отправлялся на такую почту"

        except Exception as e:
            logging.error(f"Redis error during verification: {e}")
            return "Ошибка при проверке кода"
        finally:
            try:
                await redis_ex.close()
            except Exception:
                pass

email = Email()