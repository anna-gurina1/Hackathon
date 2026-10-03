from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from backend.uploads import delete_video
from backend.email import external_url, send_email
from backend.ai_tips import AiUnavailable, generate_category_questions
from core.course_builder import recommended_questions
from core.questions import LEVELS
from database import db
from database.models import AccessRequest, CompanyProfile, Course, Enrollment, User  # noqa: F401
from database.queries import course_visible_to, search_companies, search_courses

bp = Blueprint("courses", __name__)


# ---------- helpers ----------

def _owned_course_or_abort(course_id):
    """Course owned by the current company. Person -> 403, no course -> 404,
    someone else's course -> 403."""
    if not current_user.is_company:
        abort(403)
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    if course.company_id != current_user.id:
        abort(403)
    return course


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
        "is_private": f.get("visibility") == "private",
    }
    if not data["title"]:
        return data, "Please enter a course title."
    if data["level"] not in LEVELS:
        return data, "Please choose a level."
    return data, None


def _render_form(course, status=200):
    return render_template(
        "course_form.html",
        course=course,
        LEVELS=LEVELS,
        recommended=recommended_questions(None),
    ), status


def _render_course(course, invite_token=None):
    """invite_token: set when the page was opened with the private invite link
    (then the person can start right away, without a request)."""
    is_owner = current_user.is_authenticated and course.company_id == current_user.id
    enrollment = None
    access_request = None
    if current_user.is_authenticated and current_user.is_person:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id
        ).first()
        access_request = AccessRequest.query.filter_by(
            user_id=current_user.id, course_id=course.id
        ).first()
    invite_url = None
    if is_owner and course.is_private:
        invite_url = external_url("courses.private", token=course.invite_token)
    return render_template(
        "course.html",
        course=course,
        lessons=course.lessons,
        enrollment=enrollment,
        is_owner=is_owner,
        invite_url=invite_url,
        invite_token=invite_token,
        access_request=access_request,
    )


# ---------- create / edit / delete / publish (company owner) ----------

@bp.route("/course/new", methods=["GET", "POST"])
@login_required
def new():
    if not current_user.is_company:
        abort(403)
    if request.method == "POST":
        data, error = _read_form()
        if error:
            flash(error, "error")
            return _render_form(None, 400)
        course = Course(company_id=current_user.id, **data)
        db.session.add(course)
        db.session.commit()
        return redirect(url_for("builder.script", course_id=course.id))
    return _render_form(None)


@bp.route("/course/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
def edit(course_id):
    course = _owned_course_or_abort(course_id)
    if request.method == "POST":
        data, error = _read_form()
        if error:
            flash(error, "error")
            return _render_form(course, 400)
        for key, value in data.items():
            setattr(course, key, value)
        db.session.commit()
        flash("Course saved.", "success")
        return redirect(url_for("builder.script", course_id=course.id))
    return _render_form(course)


@bp.route("/course/<int:course_id>/delete", methods=["POST"])
@login_required
def delete(course_id):
    course = _owned_course_or_abort(course_id)
    video_ids = [lesson.video_filename for lesson in course.lessons]
    db.session.delete(course)
    db.session.commit()
    # videos are removed only after the course is really gone from the database
    for public_id in video_ids:
        delete_video(public_id)
    flash("Course deleted.", "info")
    return redirect(url_for("main.account"))


@bp.route("/course/<int:course_id>/publish", methods=["POST"])
@login_required
def publish(course_id):
    course = _owned_course_or_abort(course_id)
    course.status = "published"
    db.session.commit()
    flash("Course published.", "success")
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
    if course is None:
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
    existing = AccessRequest.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if existing is not None:
        if existing.status == "declined":
            flash("The company has already declined your request for this course.", "info")
        return back

    db.session.add(AccessRequest(user_id=current_user.id, course_id=course.id))
    db.session.commit()
    send_email(
        course.company.email,
        f"New request to join “{course.title}”",
        f"{current_user.display_name} ({current_user.email}) asks to join your private course "
        f"“{course.title}”.\n\nAccept or decline the request in your account:\n"
        f"{external_url('main.account')}\n",
    )
    flash(f"Request sent. {course.company.display_name} will review it — we'll email you the answer.", "success")
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
    from datetime import datetime

    course, access_request = _owned_request_or_abort(course_id, request_id)
    if access_request.status != "accepted":
        access_request.status = "accepted"
        access_request.decided_at = datetime.utcnow()
        if not Enrollment.query.filter_by(user_id=access_request.user_id, course_id=course.id).first():
            db.session.add(Enrollment(user_id=access_request.user_id, course_id=course.id))
        db.session.commit()
        person = access_request.user
        send_email(
            person.email,
            f"You can start “{course.title}”",
            f"Hi {person.display_name},\n\n{course.company.display_name} accepted your request. "
            f"Start the course here:\n{external_url('courses.view', course_id=course.id)}\n",
        )
        flash(f"{person.display_name} can start the course now.", "success")
    return redirect(url_for("main.account") + "#requests")


@bp.route("/course/<int:course_id>/requests/<int:request_id>/decline", methods=["POST"])
@login_required
def decline_request(course_id, request_id):
    from datetime import datetime

    course, access_request = _owned_request_or_abort(course_id, request_id)
    if access_request.status == "pending":
        access_request.status = "declined"
        access_request.decided_at = datetime.utcnow()
        db.session.commit()
        person = access_request.user
        send_email(
            person.email,
            f"Your request to “{course.title}”",
            f"Hi {person.display_name},\n\nUnfortunately {course.company.display_name} declined your "
            f"request to join “{course.title}”. You can find other courses here:\n"
            f"{external_url('main.explore')}\n",
        )
        flash("Request declined.", "info")
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
    invited = course.is_private and request.form.get("invite") == course.invite_token
    if not invited and not course_visible_to(course, current_user):
        if course.is_private and course.status == "published":
            flash("This is a private course. Send a request to join it.", "info")
            return redirect(url_for("courses.view", course_id=course.id))
        abort(404)
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=course.id
    ).first()
    if enrollment is None:
        if not course.lessons:
            flash("This course has no lessons yet.", "error")
            return redirect(url_for("courses.view", course_id=course.id))
        enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
        db.session.add(enrollment)
        db.session.commit()
        return redirect(url_for("courses.lesson", course_id=course.id, n=1))
    # already enrolled: continue where the person stopped
    return redirect(
        url_for("courses.lesson", course_id=course.id, n=min(enrollment.current_lesson, course.lesson_count) or 1)
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
    if enrollment is None:
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
    )


@bp.route("/media/<path:filename>")
@login_required
def media(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# ---------- companies / search ----------

@bp.route("/company/<int:company_id>")
def company_profile(company_id):
    company = db.session.get(User, company_id)
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
    q = request.args.get("q", "").strip()
    by = request.args.get("by", "topic")
    # "Company" finds companies (the card opens the company page);
    # everything else finds courses (the card opens the course).
    if by == "company":
        companies = search_companies(q, by)
        for company in companies:
            company["type"] = "company"
        return jsonify(companies)
    return jsonify(search_courses(q, by))

# ---------- AI suggestions for the "Need ideas?" panel ----------

def _ai_questions_response(fields):
    """One AI question per topic of the panel, as JSON."""
    categories = [(g["category"], g["category_label"]) for g in recommended_questions(None)]
    try:
        questions = generate_category_questions(fields, categories)
    except AiUnavailable:
        return jsonify(error="unavailable"), 503
    return jsonify(questions=questions)


@bp.route("/api/ai-suggestions", methods=["POST"])
@login_required
def ai_suggestions():
    """New course page: the AI reads what the company typed in the form.
    JSON in: {title, description, topic, profession, outcome, level}"""
    if not current_user.is_company:
        abort(403)
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
    """Course page: the AI reads the saved course (only its owner may ask)."""
    course = _owned_course_or_abort(course_id)
    fields = {
        "title": course.title,
        "description": course.description,
        "topic": course.topic,
        "profession": course.profession,
        "outcome": course.outcome,
    }
    fields = {name: (value or "").strip()[:500] for name, value in fields.items()}
    # the title always exists, so "nothing entered" means: no topic, profession, description, outcome
    if not any(fields[name] for name in ("description", "topic", "profession", "outcome")):
        return jsonify(error="empty"), 400
    fields["level"] = LEVELS.get(course.level, "")
    return _ai_questions_response(fields)
