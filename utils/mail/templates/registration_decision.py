from utils.mail.templates.base import render_email_layout


def get_registration_decision_html(
    nickname: str,
    *,
    approved: bool,
    rejection_reason: str | None = None,
) -> str:
    display_name = nickname.strip() or "пользователь"

    if approved:
        title = "Регистрация одобрена"
        content_html = f"""
        <p style="margin: 0 0 12px; color: #1f2937; font-size: 15px; line-height: 1.6;">Здравствуйте, {display_name}.</p>
        <p style="margin: 0 0 12px; color: #1f2937; font-size: 15px; line-height: 1.6;">Администратор одобрил вашу заявку.</p>
        <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.6;">Теперь можно войти в приложение с вашим email и паролем.</p>
        """
    else:
        reason_html = ""
        if rejection_reason and rejection_reason.strip():
            reason_html = f"""
            <div style="margin: 16px 0; padding: 14px 16px; border-radius: 12px; background-color: #f8fafc; border: 1px solid #e5e7eb;">
              <div style="margin-bottom: 6px; color: #6b7280; font-size: 13px;">Причина отклонения</div>
              <div style="color: #1f2937; font-size: 14px; line-height: 1.6;">{rejection_reason.strip()}</div>
            </div>
            """

        title = "Регистрация отклонена"
        content_html = f"""
        <p style="margin: 0 0 12px; color: #1f2937; font-size: 15px; line-height: 1.6;">Здравствуйте, {display_name}.</p>
        <p style="margin: 0 0 12px; color: #1f2937; font-size: 15px; line-height: 1.6;">Администратор отклонил вашу заявку.</p>
        {reason_html}
        <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.6;">При необходимости вы можете подать заявку повторно.</p>
        """

    return render_email_layout(
        title=title,
        intro="",
        content_html=content_html,
    )
