from config.settings import settings


def render_email_layout(*, title: str, intro: str, content_html: str) -> str:
    app_name = settings.APP_NAME
    intro_html = ""
    if intro.strip():
        intro_html = (
            f'<p style="margin: 0 0 16px; color: #4b5563; font-size: 15px; line-height: 1.6;">{intro}</p>'
        )
    return f"""
    <html>
      <body style="margin: 0; padding: 24px 12px; background-color: #f3f6fb; font-family: Arial, Helvetica, sans-serif; color: #1f2937;">
        <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 18px; overflow: hidden;">
          <div style="padding: 24px 24px 16px; background-color: #6E9BD8;">
            <div style="color: #ffffff; font-size: 14px; font-weight: 700; letter-spacing: 0.2px;">{app_name}</div>
            <h1 style="margin: 12px 0 0; color: #ffffff; font-size: 24px; line-height: 1.2;">{title}</h1>
          </div>
          <div style="padding: 24px;">
            {intro_html}
            {content_html}
          </div>
          <div style="padding: 16px 24px 24px; color: #6b7280; font-size: 13px; line-height: 1.5;">
            <p style="margin: 0;">Это письмо отправлено сервисом {app_name}.</p>
          </div>
        </div>
      </body>
    </html>
    """
