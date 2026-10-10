import os

from dotenv import load_dotenv

# Project root (the folder with run.py)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Read settings (MAIL_*, SECRET_KEY, ...) from the .env file in the project root.
# This must happen BEFORE the Config class below, which reads os.environ.
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "app.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB, for course videos

    # Public address of the site, used in links inside emails (login link, invite link).
    # Empty = the address the browser used (e.g. http://127.0.0.1:5000, works only on this computer).
    # Set it to the address other people can open, e.g. https://abc123.ngrok-free.app
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")

    # Email. Leave MAIL_SERVER empty in development: emails are printed to the console.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"  # STARTTLS (port 587)
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "0") == "1"  # SSL from the start (port 465)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    # Empty = send from MAIL_USERNAME. A made-up address (e.g. noreply@bitwise.local) that does not
    # belong to the mail server is a common reason why letters land in spam.
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Bitwise")  # the name people see as the sender
    # 1 = send in a background thread (the page does not wait for the mail server).
    MAIL_BACKGROUND = os.environ.get("MAIL_BACKGROUND", "1") == "1"