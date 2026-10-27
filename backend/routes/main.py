from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, logout_user

from backend import plans
from backend.access import require_company_owner
from backend.ai_tips import AiUnavailable
from backend.i18n import COOKIE_MAX_AGE, COOKIE_NAME, LANGUAGES, _, safe_next_url
from database import db
from backend.uploads import delete_image, save_image
from database.models import (
    AccessRequest,
    Course,
    Enrollment,
    Offer,
    PersonProfile,
    QuizAttempt,
    Company,
    Membership,
    CourseEditor,
    CompanyInvitation,
)
from backend.catalog import CatalogFilters, catalog_results
from database.catalog import published_topics, search_courses
from database.queries import company_dashboard, person_dashboard
from backend.translator import translate_sources

bp = Blueprint("main", __name__)

# one page never has more "Translate" buttons than this (a long quiz is about 20)
MAX_SOURCES_PER_REQUEST = 60


@bp.route("/")
def home():
    return render_template(
        "home.html", featured_courses=search_courses("", "topic", limit=3)
    )


@bp.route("/explore")
def explore():
    filters = CatalogFilters.from_args(request.args, fallback_to_topic=True)
    return render_template(
        "explore.html",
        results=catalog_results(filters),
        topics=published_topics(),
        search_by=filters.mode,
        query=filters.query,
        selected_topic=filters.topic,
        language_filter=filters.language,
    )


@bp.route("/language/<code>")
def set_language(code):
    """The EN / RU switch in the header. Remembers the choice and goes back to the same page."""
    if code not in LANGUAGES:
        abort(404)
    response = redirect(safe_next_url(request.args.get("next"), url_for("main.home")))
    response.set_cookie(COOKIE_NAME, code, max_age=COOKIE_MAX_AGE, samesite="Lax")
    if current_user.is_authenticated and current_user.language != code:
        current_user.language = code  # emails to this person will come in this language
        db.session.commit()
    return response


@bp.route("/api/translate", methods=["POST"])
def translate():
    """The "Translate" button. {"sources": ["<signed token>", ...]} ->
    {"translations": [["...", ...], ...]} (one list per token) in the language of the site.
    main.js sends the pressed button first and then, in the background, all the other buttons
    of the page in one request, so they open at once. Open to everybody, guests too."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="bad_source"), 400
    sources = data.get("sources")
    if (
        not isinstance(sources, list)
        or not sources
        or len(sources) > MAX_SOURCES_PER_REQUEST
        or any(not isinstance(source, str) or not source for source in sources)
    ):
        return jsonify(error="bad_source"), 400
    try:
        translations = translate_sources(sources)
    except ValueError:  # broken or very old token: the page should be reloaded
        return jsonify(error="bad_source"), 400
    except AiUnavailable:  # no AI key, network problem, used-up quota...
        return jsonify(error="unavailable"), 503
    return jsonify(translations=translations)


@bp.route("/pricing")
def pricing():
    current_plan = (
        plans.plan_of(current_user)
        if current_user.is_authenticated and current_user.is_company
        else None
    )
    return render_template("pricing.html", current_plan=current_plan)


@bp.route("/pricing/choose", methods=["POST"])
@login_required
def choose_plan():
    """Demo payment: no money is taken, the button just switches the plan of the company."""
    require_company_owner()
    plan = request.form.get("plan", "")
    if plan not in plans.PLAN_LABELS:
        abort(400)

    company = current_user.company
    company.plan = plan
    if plan == "per_course":
        company.course_credits = (
            company.course_credits or 0
        ) + 1  # one more course bought
    # "free": courses are not deleted; new ones just cannot be created until the company fits the limit
    db.session.commit()
    flash(_("Plan updated: {plan}.", plan=_(plans.PLAN_LABELS[plan])), "success")
    return redirect(url_for("main.account"))


@bp.route("/account")
@login_required
def account():
    company = current_user.company
    if company is None:
        return render_template(
            "account_person.html", user=current_user, **person_dashboard(current_user)
        )
    membership = Membership.query.filter_by(
        user_id=current_user.id, company_id=company.id
    ).first()
    if membership.role == "editor":
        courses = (
            Course.query.join(CourseEditor)
            .filter(
                CourseEditor.membership_id == membership.id,
                Course.company_id == company.id,
            )
            .all()
        )
        return render_template("account_editor.html", company=company, courses=courses)
    return render_template(
        "account_company.html",
        user=company,
        plan_label=_(plans.PLAN_LABELS[plans.plan_of(company)]),
        course_limit=plans.course_limit(company),
        courses_used=plans.courses_used(company),
        can_create_course=plans.can_create_course(company),
        **company_dashboard(company)
    )


@bp.route("/account/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Change the name (person) or the name and description (company). Email stays as is."""
    if request.method == "POST":
        form = request.form
        first = form.get("first_name", "").strip()
        last = form.get("last_name", "").strip()
        if not first or not last or len(first) > 60 or len(last) > 60:
            flash(_("Enter your first and last name."), "error")
            return (
                render_template("profile_edit.html", user=current_user, form=form),
                400,
            )
        profile = current_user.person
        if profile is None:
            profile = current_user.person = PersonProfile(
                first_name=first, last_name=last
            )
        profile.first_name, profile.last_name = first, last
        db.session.commit()
        flash(_("Profile saved."), "success")
        return redirect(url_for("main.account"))
    return render_template("profile_edit.html", user=current_user, form={})


# ---------- profile photo / company logo ----------


@bp.route("/account/avatar", methods=["POST"])
@login_required
def upload_avatar():
    """Profile photo (person) or logo (company). Replaces the old one."""
    try:
        public_id = save_image(request.files.get("avatar"))
    except (
        ValueError,
        RuntimeError,
    ) as error:  # RuntimeError: Cloudinary is not configured
        flash(str(error), "error")
        return redirect(url_for("main.edit_profile"))

    old = current_user.avatar
    current_user.avatar = public_id
    db.session.commit()
    if old:
        delete_image(old)
    flash(
        _("Photo updated.") if current_user.is_person else _("Logo updated."), "success"
    )
    return redirect(url_for("main.edit_profile"))


@bp.route("/account/avatar/delete", methods=["POST"])
@login_required
def delete_avatar():
    old = current_user.avatar
    if old:
        current_user.avatar = None
        db.session.commit()
        delete_image(old)
        flash(
            _("Photo removed.") if current_user.is_person else _("Logo removed."),
            "info",
        )
    return redirect(url_for("main.edit_profile"))


# ---------- delete the account ----------


@bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    """Delete the account for good. The user types their email to confirm.
    Person: their progress, quiz results and received offers are deleted.
    Company: all its courses (with lessons, quizzes, videos, learners' progress) are deleted.
    """
    user = current_user._get_current_object()
    typed = request.form.get("confirm_email", "").strip().lower()
    if typed != user.email.lower():
        flash(_("The email does not match. Your account was not deleted."), "error")
        return redirect(url_for("main.account") + "#delete-account")

    if Company.query.filter_by(owner_id=user.id).first():
        flash(
            _(
                "Delete your companies explicitly before deleting your personal account."
            ),
            "error",
        )
        return redirect(url_for("workspaces.index"))
    membership_ids = [
        member.id for member in Membership.query.filter_by(user_id=user.id)
    ]
    if membership_ids:
        CourseEditor.query.filter(
            CourseEditor.membership_id.in_(membership_ids)
        ).delete(synchronize_session=False)
    Membership.query.filter_by(user_id=user.id).delete()
    CompanyInvitation.query.filter_by(email=user.email).delete()
    QuizAttempt.query.filter_by(user_id=user.id).delete()
    AccessRequest.query.filter_by(user_id=user.id).delete()
    Enrollment.query.filter_by(user_id=user.id).delete()
    Offer.query.filter_by(user_id=user.id).delete()

    avatar = user.avatar
    logout_user()
    session.pop("active_company_id", None)
    db.session.delete(user)  # the profile is deleted with the user
    db.session.commit()

    # files are removed only after the data is really gone from the database
    if avatar:
        delete_image(avatar)

    flash(_("Your account has been deleted."), "info")
    return redirect(url_for("main.home"))
