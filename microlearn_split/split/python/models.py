from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    """One table for both account types: 'person' and 'company'."""

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10), nullable=False)  # 'person' | 'company'
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Person fields
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))

    # Company fields
    company_name = db.Column(db.String(120))
    description = db.Column(db.String(500))

    @property
    def is_company(self):
        return self.role == "company"

    @property
    def display_name(self):
        if self.is_company:
            return self.company_name
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self):
        if self.is_company:
            return (self.company_name or "?")[:2].upper()
        first = (self.first_name or "?")[0]
        last = (self.last_name or "")[:1]
        return (first + last).upper()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
