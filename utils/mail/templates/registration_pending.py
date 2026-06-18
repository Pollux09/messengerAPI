from utils.mail.templates.base import render_email_layout


def get_registration_pending_html(nickname: str) -> str:
    display_name = nickname.strip() or "пользователь"
    return render_email_layout(
        title="Заявка принята",
        intro=f"Здравствуйте, {display_name}.",
        content_html="""
        <p style="margin: 0 0 12px; color: #1f2937; font-size: 15px; line-height: 1.6;">Почта подтверждена, а заявка передана администратору на рассмотрение.</p>
        <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.6;">Когда решение будет принято, мы сразу отправим вам новое письмо.</p>
        """,
    )
