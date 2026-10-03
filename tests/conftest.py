import re

import pytest

from core import create_app
from core.config import Config


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False  # forms in tests are sent without the CSRF token
    SERVER_NAME = "localhost"
    MAIL_SERVER = ""  # never send real emails from tests: they are printed instead
    PUBLIC_URL = ""


@pytest.fixture
def app():
    return create_app(TestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()


def find_login_link(text):
    """Pull the login link out of the email printed to the console."""
    match = re.search(r"http://localhost(/login/\S+)", text)
    return match.group(1) if match else None


def find_confirm_link(text):
    """Pull the sign-up confirmation link out of the email printed to the console."""
    match = re.search(r"http://localhost(/signup/confirm/\S+)", text)
    return match.group(1) if match else None


def signup_confirmed(client, data, follow_redirects=False):
    """Sign up like a real person: the account exists (and the person is logged in)
    only after the link from the email is opened. This helper skips the email and
    opens the link directly; test_auth.py checks the whole email flow."""
    from backend.routes.site_auth import make_signup_token

    payload = dict(data, email=data["email"].strip().lower())
    with client.application.app_context():
        token = make_signup_token(payload)
    return client.get(f"/signup/confirm/{token}", follow_redirects=follow_redirects)
