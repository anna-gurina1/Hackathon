from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from database import db
from backend.uploads import delete_video
from database.models import CompanyProfile, Enrollment, Offer, PersonProfile, QuizAttempt
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


@bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    """Delete the account for good. The user types their email to confirm.
    Person: their progress, quiz results and received offers are deleted.
    Company: all its courses (with lessons, quizzes, videos, learners' progress) are deleted."""
    user = current_user._get_current_object()
    typed = request.form.get("confirm_email", "").strip().lower()
    if typed != user.email.lower():
        flash("The email does not match. Your account was not deleted.", "error")
        return redirect(url_for("main.account") + "#delete-account")

    video_ids = []
    if user.is_company:
        from database.models import Course

        for course in Course.query.filter_by(company_id=user.id).all():
            video_ids += [lesson.video_filename for lesson in course.lessons if lesson.video_filename]
            db.session.delete(course)  # lessons, quizzes, enrollments, offers go with it
        Offer.query.filter_by(company_id=user.id).delete()
    else:
        QuizAttempt.query.filter_by(user_id=user.id).delete()
        Enrollment.query.filter_by(user_id=user.id).delete()
        Offer.query.filter_by(user_id=user.id).delete()

    logout_user()
    db.session.delete(user)  # the profile is deleted with the user
    db.session.commit()

    # videos are removed only after the data is really gone from the database
    for public_id in video_ids:
        delete_video(public_id)

    flash("Your account has been deleted.", "info")
    return redirect(url_for("main.home"))


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