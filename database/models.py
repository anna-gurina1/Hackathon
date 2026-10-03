import secrets
from datetime import datetime, timezone

from flask_login import UserMixin

from database import db


def _now():
    return datetime.now(timezone.utc)


def _new_nonce():
    return secrets.token_hex(8)


class User(UserMixin, db.Model):
    """Account. type = 'person' or 'company'. Details live in the profile tables."""

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)  # 'person' | 'company'
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    # Changes every time a login link is used, so each link works only once.
    login_nonce = db.Column(db.String(32), default=_new_nonce, nullable=False)

    person = db.relationship(
        "PersonProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    company = db.relationship(
        "CompanyProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_company(self):
        return self.type == "company"

    @property
    def is_person(self):
        return self.type == "person"

    @property
    def display_name(self):
        if self.is_company:
            return self.company.name if self.company else self.email
        if self.person:
            return f"{self.person.first_name} {self.person.last_name}".strip()
        return self.email

    @property
    def initials(self):
        if self.is_company:
            # Company: first letter of the name
            return (self.company.name if self.company else "?")[:1].upper()
        if not self.person:
            return "?"
        first = (self.person.first_name or "?")[:1]
        last = (self.person.last_name or "")[:1]
        return (first + last).upper()

    def rotate_login_nonce(self):
        self.login_nonce = _new_nonce()


class PersonProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)


class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500))
