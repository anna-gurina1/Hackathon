import re

from flask import Blueprint, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.email import external_url, send_email
from database import db
from database.models import CompanyProfile, PersonProfile, User

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LINK_MAX_AGE = 15 * 60  # login link is valid for 15 minutes


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="login-link")


def _back_to_form(message, tab):
    """Show an error and reopen the login / sign-up window on the right tab."""
    flash(message, "error")
    return redirect(url_for("main.home", auth=tab))


def send_login_link(user):
    token = _serializer().dumps({"id": user.id, "n": user.login_nonce})
    link = external_url("auth.magic_login", token=token)
    return send_email(
        user.email,
        "Your login link",
        f"Hi {user.display_name},\n\n"
        f"Click the link to log in (valid for 15 minutes, works once):\n{link}\n",
    )


@bp.route("/signup", methods=["POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = request.form
    account_type = form.get("type", "")
    email = form.get("email", "").strip().lower()

    if account_type not in ("person", "company"):
        return _back_to_form("Choose: person or company.", "signup")
    if not EMAIL_RE.match(email):
        return _back_to_form("Enter a valid email.", "signup")
    if User.query.filter_by(email=email).first():
        return _back_to_form("An account with this email already exists. Log in instead.", "login")

    user = User(type=account_type, email=email)

    if account_type == "person":
        first = form.get("first_name", "").strip()
        last = form.get("last_name", "").strip()
        if not first or not last:
            return _back_to_form("Enter your first and last name.", "signup")
        user.person = PersonProfile(first_name=first[:60], last_name=last[:60])
    else:
        name = form.get("company_name", "").strip()
        description = form.get("description", "").strip()
        if not name:
            return _back_to_form("Enter the company name.", "signup")
        user.company = CompanyProfile(name=name[:120], description=description[:500] or None)

    db.session.add(user)
    db.session.commit()

    login_user(user)
    flash(f"Welcome, {user.display_name}!", "success")
    return redirect(url_for("main.home"))


@bp.route("/login", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    email = request.form.get("email", "").strip().lower()
    if not EMAIL_RE.match(email):
        return _back_to_form("Enter a valid email.", "login")

    user = User.query.filter_by(email=email).first()
    if not user:
        return _back_to_form("No account with this email. Sign up first.", "signup")

    if not send_login_link(user):
        return _back_to_form("Could not send the email right now. Try again later.", "login")
    flash(f"We sent a login link to {email}. Check your inbox.", "info")
    return redirect(url_for("main.home"))


@bp.route("/login/<token>")
def magic_login(token):
    try:
        data = _serializer().loads(token, max_age=LINK_MAX_AGE)
    except SignatureExpired:
        return _back_to_form("This login link has expired. Request a new one.", "login")
    except BadSignature:
        return _back_to_form("This login link is not valid.", "login")

    user = db.session.get(User, data.get("id"))
    if not user or user.login_nonce != data.get("n"):
        return _back_to_form("This login link was already used. Request a new one.", "login")

    user.rotate_login_nonce()  # the link works only once
    db.session.commit()

    login_user(user, remember=True)
    flash("You are logged in.", "success")
    return redirect(url_for("main.home"))


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))