def get_confirm_email_html(email_code: str) -> str:
    return f"""
    <html>
        <body style="margin: 0; padding: 0; font-family: Arial, Helvetica, sans-serif; background-color: #f4f7fa;">
            <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="background-color: #19A3FE; padding: 20px; text-align: center;">
                    <h1 style="color: #ffffff; font-size: 24px; margin: 10px 0 0; font-weight: 600;">Подтверждение почты</h1>
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
