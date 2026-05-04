"""SMTP 経由でメール送信(Gmail SMTP リレー想定)。

Resend を使わず、個人 / Workspace の Gmail を SMTP リレーとして使う実装。
完全無料(月 3000 通制限の代わりに 1 日 500 通制限)、ドメイン認証不要、
Gmail の高い信頼性で迷惑メール判定されにくい。

設定(.env):
    MARKETER_SMTP_HOST=smtp.gmail.com
    MARKETER_SMTP_PORT=587
    MARKETER_SMTP_USER=your-gmail@gmail.com
    MARKETER_SMTP_PASSWORD=<Gmail アプリパスワード(空白なし 16 文字)>
    MARKETER_MAIL_FROM=your-gmail@gmail.com   ←普段の SMTP_USER と同じ Gmail にすると安全
    MARKETER_MAIL_NOTIFY_TO=...

Gmail アプリパスワード発行:
    1. https://myaccount.google.com/security で 2 段階認証を有効化
    2. https://myaccount.google.com/apppasswords でアプリパスワード発行
    3. 16 文字を MARKETER_SMTP_PASSWORD に設定(スペース無しでも有りでも可)
"""

import smtplib
from email.message import EmailMessage

from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def send(*, to: str, subject: str, html: str) -> None:
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
        log.warning(
            "smtp_config_unset",
            subject=subject,
            host_set=bool(settings.smtp_host),
            user_set=bool(settings.smtp_user),
            password_set=bool(settings.smtp_password),
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.mail_from or settings.smtp_user
    msg["To"] = to
    msg.set_content("HTML 表示できないメーラー向けのテキスト版です。")
    msg.add_alternative(html, subtype="html")

    # Gmail アプリパスワードがスペース付きでコピペされても動くよう正規化
    password = settings.smtp_password.replace(" ", "")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.smtp_user, password)
            smtp.send_message(msg)
        log.info("mail_sent_smtp", to=to, subject=subject)
    except Exception as exc:
        log.warning(
            "mail_send_failed_smtp",
            to=to,
            error=str(exc),
            error_type=type(exc).__name__,
        )
