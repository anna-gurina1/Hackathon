"""Sending emails.

In development (MAIL_SERVER is empty) the email is printed to the console
instead of being sent, so login links can be copied from the terminal.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, body):
    """Send an email. Returns True on success, False if sending failed."""
    cfg = current_app.config

    if not cfg.get("MAIL_SERVER"):
        print("\n" + "=" * 60)
        print(f"EMAIL to: {to}")
        print(f"Subject:  {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60 + "\n", flush=True)
        return True

    msg = EmailMessage()
    msg["From"] = cfg.get("MAIL_FROM") or cfg.get("MAIL_USERNAME")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if cfg.get("MAIL_USE_SSL"):
            smtp = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15)
        else:
            smtp = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15)
        with smtp:
            if cfg.get("MAIL_USE_TLS") and not cfg.get("MAIL_USE_SSL"):
                smtp.starttls()
            if cfg.get("MAIL_USERNAME"):
                smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
    except Exception:
        current_app.logger.exception("Could not send email to %s", to)
        return False
    return True