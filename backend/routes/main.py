from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database import db
from database.models import CompanyProfile, PersonProfile
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


@bp.route("/account/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Change the name (person) or the name and description (company). Email stays as is."""
    if request.method == "POST":
        form = request.form
        if current_user.is_person:
            first = form.get("first_name", "").strip()
            last = form.get("last_name", "").strip()
            if not first or not last:
                flash("Enter your first and last name.", "error")
                return render_template("profile_edit.html", user=current_user, form=form)
            profile = current_user.person
            if profile is None:
                profile = current_user.person = PersonProfile(first_name=first, last_name=last)
            profile.first_name = first[:60]
            profile.last_name = last[:60]
        else:
            name = form.get("company_name", "").strip()
            description = form.get("description", "").strip()
            if not name:
                flash("Enter the company name.", "error")
                return render_template("profile_edit.html", user=current_user, form=form)
            profile = current_user.company
            if profile is None:
                profile = current_user.company = CompanyProfile(name=name)
            profile.name = name[:120]
            profile.description = description[:500] or None
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("main.account"))
    return render_template("profile_edit.html", user=current_user, form={})
