from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from backend.access import (
    require_course,
    require_company_owner,
    owns_company,
    can_edit_course,
    publication_errors,
)
from backend.plans import can_create_course
from backend.uploads import delete_document, delete_video, document_url
from backend.email import external_url, send_email
from backend.i18n import _, current_language, use_language
from backend.ai_tips import AiUnavailable, generate_category_questions
from core.course_builder import recommended_questions
from core.questions import LEVELS
from core.clock import utc_now
from database import db
from database.models import (
    AccessRequest,
    Company,
    Course,
    CourseDocument,
    CourseEditor,
    Enrollment,
)
from backend.catalog import CatalogFilters, catalog_results
from database.queries import course_visible_to

bp = Blueprint("courses", __name__)


# ---------- helpers ----------


def _owned_course_or_abort(course_id):
    return require_course(course_id, owner_only=True)


def _read_form():
    """Reads and validates the course form. Returns (data, error)."""
    f = request.form
    data = {
        "title": f.get("title", "").strip(),
        "description": f.get("description", "").strip(),
        "topic": f.get("topic", "").strip(),
        "profession": f.get("profession", "").strip(),
        "outcome": f.get("outcome", "").strip(),
        "level": f.get("level", ""),
        "access_mode": (
            "public" if f.get("visibility", "public") == "public" else "request"
        ),
        "is_private": f.get("visibility", "public") != "public",
    }
    if f.get("visibility", "public") not in ("public", "private", "request", "invite"):
        return data, _("Choose a valid course visibility.")
    for field, maximum in (("title", 200), ("topic", 100), ("profession", 100)):
        if len(data[field]) > maximum:
            return data, _("A course field is too long.")
    if not data["title"]:
        return data, _("Please enter a course title.")
    if data["level"] not in LEVELS:
        return data, _("Please choose a level.")
    return data, None


def _apply_plan_rules(data, company):
    if data["is_private"] and not company.is_pro:
        return _(
            "Private courses require a paid demo plan. Your visibility choice was not changed."
        )
    return None


def _no_free_course_slot():
    """Redirect to the pricing page when the company has used all courses of its plan, else None."""
    if can_create_course(require_company_owner()):
        return None
    flash(
        _("You have used all courses on your plan. Choose a plan to add more."), "info"
    )
    return redirect(url_for("main.pricing"))


def _render_form(course, status=200):
    extra = {}
    if course is not None:
        # the master's ticks "I have answered this question" (only on an existing course)
        extra["answered_question_ids"] = {
            note.question_id for note in course.answered_questions
        }
    return (
        render_template(
            "course_form.html",
            course=course,
            LEVELS=LEVELS,
            form=request.form if request.method == "POST" else {},
            recommended=recommended_questions(None),
            **extra,
        ),
        status,
    )


def _render_course(course, invite_token=None):
    """invite_token: set when the page was opened with the private invite link
    (then the person can start right away, without a request)."""
    is_owner = owns_company(course.company_id)
    enrollment = None
    access_request = None
    if current_user.is_authenticated and current_user.is_person:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id
        ).first()
        access_request = AccessRequest.query.filter_by(
            user_id=current_user.id, course_id=course.id
        ).first()
    can_manage = can_edit_course(course)
    # PDF materials: managers and enrolled learners see them, everyone else only sees how many there are
    can_open_documents = can_manage or (
        enrollment is not None and course.status == "published"
    )
    invite_url = None
    if is_owner and course.is_private and course.status == "published":
        invite_url = external_url("courses.private", token=course.invite_token)
    return render_template(
        "course.html",
        course=course,
        lessons=course.lessons,
        enrollment=enrollment,
        is_owner=is_owner,
        can_manage=can_manage,
        documents=course.documents,
        can_open_documents=can_open_documents,
        invite_url=invite_url,
        invite_token=invite_token,
        access_request=access_request,
    )


# ---------- create / edit / delete / publish (company owner) ----------


@bp.route("/course/new", methods=["GET", "POST"])
@login_required
def new():
    company = require_company_owner()
    no_slot = _no_free_course_slot()
    if no_slot:
        return no_slot
    if request.method == "POST":
        data, error = _read_form()
        if error:
            flash(error, "error")
            return _render_form(None, 400)
        error = _apply_plan_rules(data, company)
        if error:
            flash(error, "error")
            return _render_form(None, 400)
        course = Course(company_id=company.id, **data)
        course.update_language()  # "en" / "ru" chip in the catalog
        db.session.add(course)
        db.session.commit()
        return redirect(url_for("builder.script", course_id=course.id))
    return _render_form(None)


@bp.route("/course/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
def edit(course_id):
    course = require_course(course_id)
    if request.method == "POST":
        data, error = _read_form()
        if error:
            flash(error, "error")
            return _render_form(course, 400)
        error = _apply_plan_rules(data, course.company)
        if error:
            flash(error, "error")
            return _render_form(course, 400)
        if (
            course.status == "published"
            and data["is_private"]
            and any(
                lesson.video_filename and lesson.video_delivery != "authenticated"
                for lesson in course.lessons
            )
        ):
            flash(
                _("Re-upload legacy public videos before restricting this course."),
                "error",
            )
            return _render_form(course, 400)
        for key, value in data.items():
            setattr(course, key, value)
        course.update_language()  # the texts could be rewritten in another language
        db.session.commit()
        flash(_("Course saved."), "success")
        return redirect(url_for("builder.script", course_id=course.id))
    return _render_form(course)


@bp.route("/course/<int:course_id>/delete", methods=["POST"])
@login_required
def delete(course_id):
    course = _owned_course_or_abort(course_id)
    video_ids = [
        (lesson.video_filename, lesson.video_delivery) for lesson in course.lessons
    ]
    document_ids = [document.public_id for document in course.documents]
    CourseEditor.query.filter_by(course_id=course.id).delete()
    db.session.delete(course)
    db.session.commit()
    # files are removed only after the course is really gone from the database
    for public_id, delivery in video_ids:
        delete_video(public_id, delivery=delivery)
    for public_id in document_ids:
        delete_document(public_id)
    flash(_("Course deleted."), "info")
    return redirect(url_for("main.account"))


@bp.route("/course/<int:course_id>/publish", methods=["POST"])
@login_required
def publish(course_id):
    course = _owned_course_or_abort(course_id)
    errors = publication_errors(course)
    if errors:
        flash(
            _("Course is not ready for publication.") + " " + " ".join(errors), "error"
        )
        return redirect(url_for("builder.script", course_id=course.id))
    course.status = "published"
    db.session.commit()
    flash(_("Course published."), "success")
    return redirect(url_for("courses.view", course_id=course.id))


# ---------- viewing ----------


@bp.route("/course/<int:course_id>")
def view(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    # A published private course has a public page too (title, description, lessons list),
    # but its lessons open only after the company accepts the request.
    if course.status != "published" and not course_visible_to(course, current_user):
        abort(404)
    return _render_course(course)


@bp.route("/course/private/<token>")
def private(token):
    course = Course.query.filter_by(invite_token=token).first()
    if course is None or course.status != "published" or not course.is_private:
        abort(404)
    return _render_course(course, invite_token=token)


# ---------- requests to private courses ----------


@bp.route("/course/<int:course_id>/request", methods=["POST"])
@login_required
def request_access(course_id):
    """A person asks to join a private course."""
    if not current_user.is_person:
        abort(403)
    course = db.session.get(Course, course_id)
    if course is None or not course.is_private or course.status != "published":
        abort(404)
    back = redirect(url_for("courses.view", course_id=course.id))

    if Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first():
        return back
    existing = AccessRequest.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    if existing is not None:
        if existing.status == "declined":
            flash(
                _("The company has already declined your request for this course."),
                "info",
            )
        return back

    db.session.add(AccessRequest(user_id=current_user.id, course_id=course.id))
    db.session.commit()
    with use_language(
        course.company.language
    ):  # the email is written in the company's language
        send_email(
            course.company.email,
            _("New request to join “{course}”", course=course.title),
            _(
                "{name} ({email}) asks to join your private course “{course}”.",
                name=current_user.display_name,
                email=current_user.email,
                course=course.title,
            )
            + "\n\n"
            + _("Accept or decline the request in your account:")
            + f"\n{external_url('main.account')}\n",
        )
    flash(
        _(
            "Request sent. {company} will review it — we'll email you the answer.",
            company=course.company.display_name,
        ),
        "success",
    )
    return back


def _owned_request_or_abort(course_id, request_id):
    course = _owned_course_or_abort(course_id)
    access_request = db.session.get(AccessRequest, request_id)
    if access_request is None or access_request.course_id != course.id:
        abort(404)
    return course, access_request


@bp.route("/course/<int:course_id>/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(course_id, request_id):

    course, access_request = _owned_request_or_abort(course_id, request_id)
    if access_request.status != "accepted":
        access_request.status = "accepted"
        access_request.decided_at = utc_now()
        if not Enrollment.query.filter_by(
            user_id=access_request.user_id, course_id=course.id
        ).first():
            db.session.add(
                Enrollment(user_id=access_request.user_id, course_id=course.id)
            )
        db.session.commit()
        person = access_request.user
        with use_language(
            person.language
        ):  # the email is written in the learner's language
            send_email(
                person.email,
                _("You can start “{course}”", course=course.title),
                _("Hi {name},", name=person.display_name)
                + "\n\n"
                + _(
                    "{company} accepted your request. Start the course here:",
                    company=course.company.display_name,
                )
                + f"\n{external_url('courses.view', course_id=course.id)}\n",
            )
        flash(
            _("{name} can start the course now.", name=person.display_name), "success"
        )
    return redirect(url_for("main.account") + "#requests")


@bp.route("/course/<int:course_id>/requests/<int:request_id>/decline", methods=["POST"])
@login_required
def decline_request(course_id, request_id):

    course, access_request = _owned_request_or_abort(course_id, request_id)
    if access_request.status == "pending":
        access_request.status = "declined"
        access_request.decided_at = utc_now()
        db.session.commit()
        person = access_request.user
        with use_language(
            person.language
        ):  # the email is written in the learner's language
            send_email(
                person.email,
                _("Your request to “{course}”", course=course.title),
                _("Hi {name},", name=person.display_name)
                + "\n\n"
                + _(
                    "Unfortunately {company} declined your request to join “{course}”. You can find other courses here:",
                    company=course.company.display_name,
                    course=course.title,
                )
                + f"\n{external_url('main.explore')}\n",
            )
        flash(_("Request declined."), "info")
    return redirect(url_for("main.account") + "#requests")


# ---------- learning ----------


@bp.route("/course/<int:course_id>/start", methods=["POST"])
@login_required
def start(course_id):
    if not current_user.is_person:
        abort(403)
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    # private course: only after the request was accepted (= enrolled) or with the invite link
    if course.status != "published" or publication_errors(course):
        abort(
            409,
            description=_(
                "This course is not ready for learning. Please contact its owner."
            ),
        )
    invited = course.is_private and request.form.get("invite") == course.invite_token
    if not invited and not course_visible_to(course, current_user):
        if course.is_private and course.status == "published":
            flash(_("This is a private course. Send a request to join it."), "info")
            return redirect(url_for("courses.view", course_id=course.id))
        abort(404)
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    if enrollment is None:
        if not course.lessons:
            flash(_("This course has no lessons yet."), "error")
            return redirect(url_for("courses.view", course_id=course.id))
        enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
        db.session.add(enrollment)
        db.session.commit()
        return redirect(url_for("courses.lesson", course_id=course.id, n=1))
    # already enrolled: continue where the person stopped
    return redirect(
        url_for(
            "courses.lesson",
            course_id=course.id,
            n=min(enrollment.current_lesson, course.lesson_count) or 1,
        )
    )


@bp.route("/course/<int:course_id>/lesson/<int:n>")
@login_required
def lesson(course_id, n):
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    if (
        enrollment is None
        or course.status != "published"
        or (
            course.is_private
            and any(
                item.video_filename and item.video_delivery != "authenticated"
                for item in course.lessons
            )
        )
    ):
        abort(403)
    if n > enrollment.current_lesson:
        abort(403)
    lesson_obj = next((l for l in course.lessons if l.order == n), None)
    if lesson_obj is None:
        abort(404)
    video_url = lesson_obj.video_url  # Cloudinary https link or None
    quiz_url = (
        url_for("quiz.take", course_id=course.id, n=n) if lesson_obj.quiz else None
    )
    return render_template(
        "lesson.html",
        course=course,
        lessons=course.lessons,
        lesson=lesson_obj,
        n=n,
        enrollment=enrollment,
        video_url=video_url,
        quiz_url=quiz_url,
        documents=course.documents,
    )


@bp.route("/course/<int:course_id>/documents/<int:document_id>")
@login_required
def document(course_id, document_id):
    """Authorized PDF download: managers and enrolled learners get a short-lived signed link."""
    course = db.session.get(Course, course_id)
    document_obj = db.session.get(CourseDocument, document_id)
    if course is None or document_obj is None or document_obj.course_id != course.id:
        abort(404)
    enrolled = (
        course.status == "published"
        and Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id
        ).first()
        is not None
    )
    if not (can_edit_course(course) or enrolled):
        abort(403)
    try:
        url = document_url(
            document_obj.public_id, download=request.args.get("download") == "1"
        )
    except RuntimeError:
        abort(503)
    response = redirect(url)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("/media/<path:filename>")
@login_required
def media(filename):
    # Legacy local files have no reliable per-course mapping. Fail closed.
    abort(404)


# ---------- companies / search ----------


@bp.route("/company/<int:company_id>")
def company_profile(company_id):
    company = db.session.get(Company, company_id)
    if company is None or not company.is_company:
        abort(404)
    courses = (  # public and private (private ones open by request)
        Course.query.filter_by(company_id=company.id, status="published")
        .order_by(Course.created_at.desc())
        .all()
    )
    return render_template("company.html", company=company, courses=courses)


@bp.route("/api/search")
def search():
    """Same search pipeline as /explore; only the response format differs."""
    filters = CatalogFilters.from_args(request.args)
    return jsonify(catalog_results(filters))


# ---------- AI suggestions for the "Need ideas?" panel ----------


def _ai_questions_response(fields):
    """One AI question per topic of the panel, as JSON."""
    categories = [
        (g["category"], g["category_label"]) for g in recommended_questions(None)
    ]
    try:
        # if the course text does not show its language, the AI writes in the language of the site
        site_language = {"en": "English", "ru": "Russian"}.get(
            current_language(), "English"
        )
        questions = generate_category_questions(
            fields, categories, fallback_language=site_language
        )
    except AiUnavailable:
        return jsonify(error="unavailable"), 503
    return jsonify(questions=questions)


@bp.route("/api/ai-suggestions", methods=["POST"])
@login_required
def ai_suggestions():
    """New course page: the AI reads what the company typed in the form.
    JSON in: {title, description, topic, profession, outcome, level}"""
    require_company_owner()
    payload = request.get_json(silent=True) or {}
    fields = {
        name: str(payload.get(name) or "").strip()[:500]
        for name in ("title", "description", "topic", "profession", "outcome")
    }
    if not any(fields.values()):
        return jsonify(error="empty"), 400
    fields["level"] = LEVELS.get(payload.get("level"), "")
    return _ai_questions_response(fields)


@bp.route("/course/<int:course_id>/ai-suggestions", methods=["POST"])
@login_required
def course_ai_suggestions(course_id):
    """Only an authorized course author may ask."""
    course = require_course(course_id)
    fields = {
        "title": course.title,
        "description": course.description,
        "topic": course.topic,
        "profession": course.profession,
        "outcome": course.outcome,
    }
    fields = {name: (value or "").strip()[:500] for name, value in fields.items()}
    # the title always exists, so "nothing entered" means: no topic, profession, description, outcome
    if not any(
        fields[name] for name in ("description", "topic", "profession", "outcome")
    ):
        return jsonify(error="empty"), 400
    fields["level"] = LEVELS.get(course.level, "")
    return _ai_questions_response(fields)


@bp.route("/course/<int:course_id>/preview/lesson/<int:lesson_id>")
@login_required
def preview_lesson(course_id, lesson_id):
    course = require_course(course_id)
    from database.models import Lesson

    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None or lesson.course_id != course.id:
        abort(404)
    return render_template("lesson_preview.html", course=course, lesson=lesson)
