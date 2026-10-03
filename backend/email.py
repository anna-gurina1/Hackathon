"""Sending emails.

In development (MAIL_SERVER is empty) the email is printed to the console
instead of being sent, so login links can be copied from the terminal.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, body):
    cfg = current_app.config

    if not cfg.get("MAIL_SERVER"):
        print("\n" + "=" * 60)
        print(f"EMAIL to: {to}")
        print(f"Subject:  {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60 + "\n", flush=True)
        return

    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as smtp:
        if cfg.get("MAIL_USE_TLS"):
            smtp.starttls()
        if cfg.get("MAIL_USERNAME"):
            smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)
