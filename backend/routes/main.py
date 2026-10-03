from flask import Blueprint, render_template
from flask_login import current_user, login_required

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