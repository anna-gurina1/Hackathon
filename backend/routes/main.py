from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from backend import plans
from database import db
from backend.uploads import delete_image, delete_video, save_image
from database.models import AccessRequest, CompanyProfile, Course, Enrollment, Offer, PersonProfile, QuizAttempt
from database.queries import company_dashboard, person_dashboard

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/explore")
def explore():
    return render_template("explore.html")


@bp.route("/pricing")
def pricing():
    current_plan = plans.plan_of(current_user) if current_user.is_authenticated and current_user.is_company else None
    return render_template("pricing.html", current_plan=current_plan)


@bp.route("/pricing/choose", methods=["POST"])
@login_required
def choose_plan():
    """Demo payment: no money is taken, the button just switches the plan of the company."""
    if not current_user.is_company or current_user.company is None:
        abort(403)
    plan = request.form.get("plan", "")
    if plan not in plans.PLAN_LABELS:
        abort(400)

    company = current_user.company
    company.plan = plan
    if plan == "per_course":
        company.course_credits = (company.course_credits or 0) + 1  # one more course bought
    # "free": courses are not deleted; new ones just cannot be created until the company fits the limit
    db.session.commit()
    flash(f"Plan updated: {plans.PLAN_LABELS[plan]}.", "success")
    return redirect(url_for("main.account"))


@bp.route("/account")
@login_required
def account():
    if current_user.is_person:
        return render_template(
            "account_person.html", user=current_user, **person_dashboard(current_user)
        )
    return render_template(
        "account_company.html",
        user=current_user,
        plan_label=plans.PLAN_LABELS[plans.plan_of(current_user)],
        course_limit=plans.course_limit(current_user),
        courses_used=plans.courses_used(current_user),
        can_create_course=plans.can_create_course(current_user),
        **company_dashboard(current_user),
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


# ---------- profile photo / company logo ----------

@bp.route("/account/avatar", methods=["POST"])
@login_required
def upload_avatar():
    """Profile photo (person) or logo (company). Replaces the old one."""
    try:
        public_id = save_image(request.files.get("avatar"))
    except (ValueError, RuntimeError) as error:  # RuntimeError: Cloudinary is not configured
        flash(str(error), "error")
        return redirect(url_for("main.edit_profile"))

    old = current_user.avatar
    current_user.avatar = public_id
    db.session.commit()
    if old:
        delete_image(old)
    flash("Photo updated." if current_user.is_person else "Logo updated.", "success")
    return redirect(url_for("main.edit_profile"))


@bp.route("/account/avatar/delete", methods=["POST"])
@login_required
def delete_avatar():
    old = current_user.avatar
    if old:
        current_user.avatar = None
        db.session.commit()
        delete_image(old)
        flash("Photo removed." if current_user.is_person else "Logo removed.", "info")
    return redirect(url_for("main.edit_profile"))


# ---------- delete the account ----------

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
        for course in Course.query.filter_by(company_id=user.id).all():
            video_ids += [lesson.video_filename for lesson in course.lessons if lesson.video_filename]
            db.session.delete(course)  # lessons, quizzes, enrollments, offers go with it
        Offer.query.filter_by(company_id=user.id).delete()
    else:
        QuizAttempt.query.filter_by(user_id=user.id).delete()
        AccessRequest.query.filter_by(user_id=user.id).delete()
        Enrollment.query.filter_by(user_id=user.id).delete()
        Offer.query.filter_by(user_id=user.id).delete()

    avatar = user.avatar
    logout_user()
    db.session.delete(user)  # the profile is deleted with the user
    db.session.commit()

    # files are removed only after the data is really gone from the database
    for public_id in video_ids:
        delete_video(public_id)
    if avatar:
        delete_image(avatar)

    flash("Your account has been deleted.", "info")
    return redirect(url_for("main.home"))