import re

from flask import Blueprint, current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from sqlalchemy.exc import IntegrityError

from backend.email import external_url, send_email
from backend.throttle import claim_email_slot
from database import db
from database.models import CompanyProfile, EmailThrottle, PersonProfile, User

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LINK_MAX_AGE = 15 * 60  # login link is valid for 15 minutes
SIGNUP_LINK_MAX_AGE = 24 * 60 * 60  # sign-up confirmation link is valid for 24 hours


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="login-link")


def _signup_serializer():
    # a different salt, so a login link can never be used as a sign-up link
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="signup-confirm")


def make_signup_token(data):
    """data: the checked sign-up form (type, email, names / company name, description).
    The account is NOT created yet: it is created when the link from the email is opened."""
    return _signup_serializer().dumps(data)


def _wait_message(seconds, what="an email"):
    return (f"We already sent {what} to this address a moment ago — check your inbox and the Spam folder. "
            f"You can request another in {seconds} s.")


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

    if account_type == "person":
        first = form.get("first_name", "").strip()
        last = form.get("last_name", "").strip()
        if not first or not last:
            return _back_to_form("Enter your first and last name.", "signup")
        data = {"type": "person", "email": email, "first_name": first[:60], "last_name": last[:60]}
    else:
        name = form.get("company_name", "").strip()
        description = form.get("description", "").strip()
        if not name:
            return _back_to_form("Enter the company name.", "signup")
        data = {
            "type": "company", "email": email,
            "company_name": name[:120], "description": description[:500],
        }

    wait = claim_email_slot(email)
    if wait:
        return _back_to_form(_wait_message(wait, "a confirmation link"), "signup")

    link = external_url("auth.confirm_signup", token=make_signup_token(data))
    send_email(
        email,
        "Confirm your email",
        "Hi,\n\n"
        "Click the link to confirm your email and finish creating your account "
        f"(valid for 24 hours):\n{link}\n\n"
        "If this was not you, just ignore this email: nothing will be created.\n",
    )
    flash(f"We sent a confirmation link to {email}. Open it to finish signing up.", "info")
    return redirect(url_for("main.home"))


@bp.route("/signup/confirm/<token>")
def confirm_signup(token):
    """The link from the sign-up email: only now the account is created and logged in."""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    try:
        data = _signup_serializer().loads(token, max_age=SIGNUP_LINK_MAX_AGE)
    except SignatureExpired:
        return _back_to_form("This confirmation link has expired. Sign up again.", "signup")
    except BadSignature:
        return _back_to_form("This confirmation link is not valid.", "signup")

    email = str(data.get("email", "")).strip().lower()
    account_type = data.get("type")
    if not EMAIL_RE.match(email) or account_type not in ("person", "company"):
        return _back_to_form("This confirmation link is not valid.", "signup")

    if User.query.filter_by(email=email).first():
        return _back_to_form("This email is already confirmed. Log in.", "login")

    user = User(type=account_type, email=email)
    if account_type == "person":
        user.person = PersonProfile(
            first_name=str(data.get("first_name", ""))[:60],
            last_name=str(data.get("last_name", ""))[:60],
        )
    else:
        user.company = CompanyProfile(
            name=str(data.get("company_name", ""))[:120],
            description=str(data.get("description", ""))[:500] or None,
        )

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # the link was opened twice at the same moment
        db.session.rollback()
        return _back_to_form("This email is already confirmed. Log in.", "login")

    login_user(user, remember=True)
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
        if db.session.get(EmailThrottle, f"auth:{email}") is not None:
            # signed up recently, but the link from the email was not opened yet
            return _back_to_form(
                f"You have not confirmed your email yet. Open the confirmation link we sent to {email} "
                "(check the Spam folder too) — your account is created only after that.",
                "signup",
            )
        return _back_to_form("No account with this email. Sign up first.", "signup")

    wait = claim_email_slot(email)
    if wait:
        return _back_to_form(_wait_message(wait, "a login link"), "login")

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