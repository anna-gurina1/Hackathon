"""Sending emails.

In development (MAIL_SERVER is empty) the email is printed to the console
instead of being sent, so login links can be copied from the terminal.

With a real SMTP server the email is sent in a background thread, so the page
does not wait for Gmail (it can take up to 15 seconds).

BREVO_API_KEY set -> the email goes through Brevo (brevo.com) as a normal HTTPS request
instead of SMTP. Use it where SMTP ports are closed, e.g. the free plan of Render
("OSError: [Errno 101] Network is unreachable" in the log). MAIL_FROM / MAIL_USERNAME is
the sender; it must be a sender verified in Brevo (Senders, domains & dedicated IPs).
"""
import json
import smtplib
import urllib.error
import urllib.request
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


BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _deliver_with_brevo(api_key, msg, logger):
    """Same as _deliver, but through the Brevo web API (HTTPS, port 443 is open everywhere)."""
    sender_name, sender_address = parseaddr(msg["From"])
    payload = {
        "sender": {"name": sender_name or "Bitwise", "email": sender_address},
        "to": [{"email": msg["To"]}],
        "subject": msg["Subject"],
        "textContent": msg.get_content(),
    }
    request = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15):
            pass
    except urllib.error.HTTPError as error:
        # e.g. 401 = wrong key, 400 = the sender is not verified in Brevo (the key is never logged)
        detail = error.read().decode("utf-8", "replace")[:300]
        logger.error("Could not send email to %s: Brevo answered %s %s", msg["To"], error.code, detail)
        return False
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
    # Without MAIL_SERVER and BREVO_API_KEY (development) they are printed too.
    if not (cfg.get("MAIL_SERVER") or cfg.get("BREVO_API_KEY")) or to.lower().endswith("@bitwise.demo"):
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

    brevo_key = cfg.get("BREVO_API_KEY")
    if brevo_key:
        deliver, arguments = _deliver_with_brevo, (brevo_key, msg, logger)
    else:
        deliver, arguments = _deliver, (settings, msg, logger)

    if cfg.get("MAIL_BACKGROUND", True):
        _executor.submit(deliver, *arguments)
        return True
    return deliver(*arguments)  # MAIL_BACKGROUND=0: wait for the result
