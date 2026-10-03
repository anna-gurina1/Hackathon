import os

from dotenv import load_dotenv

# Project root (the folder with run.py)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Read settings (MAIL_*, SECRET_KEY, ...) from the .env file in the project root
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "app.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB, for course videos

    # Email. Leave MAIL_SERVER empty in development: emails are printed to the console.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"  # STARTTLS (port 587)
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "0") == "1"  # SSL from the start (port 465)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@bitwise.local")