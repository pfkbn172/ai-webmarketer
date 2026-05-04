"""メール送信のエントリポイント(後方互換のため `resend_mailer` の名前を維持)。

実際のバックエンドは settings.mail_backend で切り替える:
- "smtp": Gmail 等の SMTP リレー(smtp_mailer.send)
- "resend": Resend API
- "auto"(デフォルト): SMTP_USER/SMTP_PASSWORD があれば SMTP、なければ Resend
"""

import resend

from app.services import smtp_mailer
from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def _decide_backend() -> str:
    if settings.mail_backend in ("smtp", "resend"):
        return settings.mail_backend
    # auto: SMTP 設定が揃っていれば SMTP、無ければ Resend、それも無ければ noop
    if settings.smtp_user and settings.smtp_password:
        return "smtp"
    if settings.resend_api_key:
        return "resend"
    return "none"


def send(*, to: str, subject: str, html: str) -> None:
    backend = _decide_backend()
    if backend == "smtp":
        smtp_mailer.send(to=to, subject=subject, html=html)
        return
    if backend == "resend":
        _send_via_resend(to=to, subject=subject, html=html)
        return
    log.warning("mail_backend_not_configured", subject=subject)


def _send_via_resend(*, to: str, subject: str, html: str) -> None:
    resend.api_key = settings.resend_api_key
    try:
        resp = resend.Emails.send(
            {
                "from": settings.mail_from,
                "to": to,
                "subject": subject,
                "html": html,
            }
        )
        log.info("mail_sent_resend", to=to, id=resp.get("id"))
    except Exception as exc:
        log.warning("mail_send_failed_resend", to=to, error=str(exc))
