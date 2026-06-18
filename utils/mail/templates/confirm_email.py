from utils.mail.templates.base import render_email_layout


def get_confirm_email_html(email_code: str) -> str:
    return render_email_layout(
        title="Подтверждение почты",
        intro="Введите код ниже, чтобы подтвердить адрес электронной почты.",
        content_html=f"""
        <div style="margin: 24px 0; text-align: center;">
          <div style="display: inline-block; padding: 16px 24px; border-radius: 14px; background-color: #eef4ff; border: 1px solid #c8d8f2;">
            <div style="color: #6E9BD8; font-size: 30px; font-weight: 700; letter-spacing: 6px;">{email_code}</div>
          </div>
        </div>
        <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.6;">Код действует 3 минуты.</p>
        <p style="margin: 16px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">Если вы не запрашивали регистрацию, просто проигнорируйте это письмо.</p>
        """,
    )
