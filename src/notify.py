"""Optional email delivery of the digest (Gmail SMTP, free).

Off by default. Turn on with `delivery.email.enabled: true` in filters.yaml and
set these env vars (GitHub: repo Settings > Secrets and variables > Actions):
  GMAIL_USER          the sending Gmail address
  GMAIL_APP_PASSWORD  a Gmail app password (not your login password) -
                       generate one at https://myaccount.google.com/apppasswords
  DIGEST_TO_EMAIL     where to send it (defaults to GMAIL_USER if unset)

Uses Gmail's SMTP relay (smtp.gmail.com:587, STARTTLS) - no third-party API,
no cost.
"""

import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def available():
    return bool(os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"))


def send_digest(subject, body_markdown):
    """Send the digest body as a plain-text email. Raises on failure so the
    caller can catch it and keep the run failing soft."""
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to_addr = os.environ.get("DIGEST_TO_EMAIL", user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body_markdown)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
