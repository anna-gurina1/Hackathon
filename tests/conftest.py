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