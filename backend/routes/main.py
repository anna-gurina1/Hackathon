from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database import db

from database.queries import company_dashboard, person_dashboard

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/explore")
def explore():
    return render_template("explore.html")


@bp.route("/account")
@login_required
def account():
    if current_user.is_person:
        return render_template(
            "account_person.html", user=current_user, **person_dashboard(current_user)
        )
    return render_template(
        "account_company.html", user=current_user, **company_dashboard(current_user)
    )


def _safe_next(target):
    """Only allow redirects to a page of this site (no https://evil.com, no //evil.com)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


@bp.route("/pro", methods=["GET", "POST"])
@login_required
def pro():
    """Pro plan page. Payment is a demo: the button just turns Pro on."""
    if not current_user.is_company:
        abort(403)
    if request.method == "POST":
        current_user.company.is_pro = True
        db.session.commit()
        flash("You are on the Pro plan now. Private courses are unlocked.", "success")
        return redirect(_safe_next(request.form.get("next")) or url_for("main.account"))
    return render_template(
        "pro.html", user=current_user, next_url=_safe_next(request.args.get("next"))
    )