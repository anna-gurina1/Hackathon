"""Sending emails.

In development (MAIL_SERVER is empty) the email is printed to the console
instead of being sent, so login links can be copied from the terminal.

With a real SMTP server the email is sent in a background thread, so the page
does not wait for Gmail (it can take up to 15 seconds).
"""
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr

from flask import current_app

# A few worker threads are enough; extra emails wait in the queue.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mail")


def external_url(endpoint, **values):
    """Full link for use inside emails. Uses PUBLIC_URL from .env when it is set,
    otherwise the address the browser used (127.0.0.1 works only on the server's own computer)."""
    from flask import url_for

    base = current_app.config.get("PUBLIC_URL")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def _deliver(settings, msg, logger):
    """Talk to the SMTP server. Runs in a worker thread, so it must not touch
    flask.request / current_app (settings and logger are passed in)."""
    try:
        if settings["MAIL_USE_SSL"]:
            smtp = smtplib.SMTP_SSL(settings["MAIL_SERVER"], settings["MAIL_PORT"], timeout=15)
        else:
            smtp = smtplib.SMTP(settings["MAIL_SERVER"], settings["MAIL_PORT"], timeout=15)
        with smtp:
            if settings["MAIL_USE_TLS"] and not settings["MAIL_USE_SSL"]:
                smtp.starttls()
            if settings["MAIL_USERNAME"]:
                smtp.login(settings["MAIL_USERNAME"], settings["MAIL_PASSWORD"])
            smtp.send_message(msg)
    except Exception:
        logger.exception("Could not send email to %s", msg["To"])
        return False
    return True


def send_email(to, subject, body):
    """Send an email.

    Returns True when the email was printed (development) or handed to the
    background sender. A delivery error in the background is only written to
    the log: the person who clicked the button has already got the page.
    """
    cfg = current_app.config

    # Demo accounts (database/seed.py) have made-up addresses: their emails are always printed.
    if not cfg.get("MAIL_SERVER") or to.lower().endswith("@bitwise.demo"):
        print("\n" + "=" * 60)
        print(f"EMAIL to: {to}")
        print(f"Subject:  {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60 + "\n", flush=True)
        return True

    # "Bitwise <address>": a sender name and the Date / Message-ID headers that every normal
    # mail program adds. Letters without them look suspicious to spam filters.
    sender_name, sender_address = parseaddr(cfg.get("MAIL_FROM") or cfg.get("MAIL_USERNAME"))
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name or cfg.get("MAIL_FROM_NAME") or "Bitwise", sender_address))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender_address.rpartition("@")[2] or None)
    msg.set_content(body)

    settings = {
        key: cfg.get(key)
        for key in (
            "MAIL_SERVER", "MAIL_PORT", "MAIL_USE_TLS", "MAIL_USE_SSL",
            "MAIL_USERNAME", "MAIL_PASSWORD",
        )
    }
    logger = current_app.logger

    if cfg.get("MAIL_BACKGROUND", True):
        _executor.submit(_deliver, settings, msg, logger)
        return True
    return _deliver(settings, msg, logger)  # MAIL_BACKGROUND=0: wait for the result
