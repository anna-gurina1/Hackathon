"""SMTP must verify server certificates before authenticating or sending mail."""

import ssl
from email.message import EmailMessage
from unittest.mock import Mock

import pytest

from backend import email


def smtp_settings(mode):
    return {
        "MAIL_SERVER": "smtp.example.invalid",
        "MAIL_PORT": 465 if mode == "ssl" else 587,
        "MAIL_USE_SSL": mode == "ssl",
        "MAIL_USE_TLS": mode == "starttls",
        "MAIL_USERNAME": "sender@example.invalid",
        "MAIL_PASSWORD": "synthetic-test-value",
    }


def message():
    result = EmailMessage()
    result["To"] = "recipient@example.invalid"
    result.set_content("Synthetic test email; never sent over a network.")
    return result


def fake_smtp(monkeypatch, mode, failure=None):
    events = []
    contexts = []

    def handshake(context):
        contexts.append(context)
        if failure is not None:
            raise failure

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            events.append("closed")

        def starttls(self, *, context=None):
            events.append("starttls")
            handshake(context)

        def login(self, *args):
            events.append("login")

        def send_message(self, msg):
            events.append("send")

    def connect(host, port, *, timeout, context=None):
        assert host == "smtp.example.invalid"
        assert timeout == 15
        events.append("connect")
        if mode == "ssl":
            handshake(context)
        return Connection()

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Unexpected SMTP transport or insecure fallback")

    monkeypatch.setattr(email.smtplib, "SMTP_SSL", connect if mode == "ssl" else unexpected_connection)
    monkeypatch.setattr(email.smtplib, "SMTP", connect if mode != "ssl" else unexpected_connection)
    return events, contexts


def assert_verified_context(contexts):
    assert len(contexts) == 1
    context = contexts[0]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


@pytest.mark.parametrize("mode", ["ssl", "starttls"])
def test_smtp_uses_verified_tls_context(monkeypatch, mode):
    events, contexts = fake_smtp(monkeypatch, mode)
    assert email._deliver(smtp_settings(mode), message(), Mock()) is True
    assert_verified_context(contexts)
    assert events[-3:] == ["login", "send", "closed"]
    if mode == "starttls":
        assert events.index("starttls") < events.index("login")


@pytest.mark.parametrize("mode", ["ssl", "starttls"])
def test_certificate_failure_never_authenticates_or_sends(monkeypatch, mode):
    events, contexts = fake_smtp(
        monkeypatch, mode, ssl.SSLCertVerificationError("Synthetic invalid certificate")
    )
    logger = Mock()
    assert email._deliver(smtp_settings(mode), message(), logger) is False
    assert_verified_context(contexts)
    assert "login" not in events and "send" not in events
    assert events.count("connect") == 1
    logger.exception.assert_called_once()


def test_missing_starttls_never_falls_back_to_plaintext(monkeypatch):
    events, contexts = fake_smtp(
        monkeypatch, "starttls", email.smtplib.SMTPNotSupportedError("Synthetic TLS unavailable")
    )
    assert email._deliver(smtp_settings("starttls"), message(), Mock()) is False
    assert_verified_context(contexts)
    assert "login" not in events and "send" not in events
    assert events.count("connect") == 1


def test_brevo_api_does_not_use_smtp(app, monkeypatch):
    app.config.update(
        BREVO_API_KEY="synthetic-api-key",
        MAIL_FROM="sender@example.invalid",
        MAIL_BACKGROUND=False,
    )
    deliver = Mock(return_value=True)
    smtp = Mock(side_effect=AssertionError("Brevo must not use SMTP"))
    monkeypatch.setattr(email, "_deliver_with_brevo", deliver)
    monkeypatch.setattr(email, "_deliver", smtp)
    assert email.send_email("recipient@example.invalid", "Test", "Synthetic body") is True
    deliver.assert_called_once()
    smtp.assert_not_called()
