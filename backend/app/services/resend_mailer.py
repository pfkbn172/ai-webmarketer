"""Resend 経由でメール送信。"""

import resend

from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def send(*, to: str, subject: str, html: str) -> None:
    if not settings.resend_api_key:
        log.warning("resend_api_key_unset", subject=subject)
        return
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
        log.info("mail_sent", to=to, id=resp.get("id"))
    except Exception as exc:
        log.warning("mail_send_failed", to=to, error=str(exc))
