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
from core.course_builder import recommended_questions
from core.questions import LEVELS
from database import db
from database.models import CompanyProfile, Course, Enrollment, User  # noqa: F401
from database.queries import course_visible_to, search_companies

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


def _apply_plan_rules(data):
    """Private courses are a Pro feature: a non-Pro company's course stays public."""
    if data["is_private"] and not current_user.is_pro:
        data["is_private"] = False
        flash("Private courses are a Pro feature. The course stays public.", "info")


def _render_form(course, status=200):
    return render_template(
        "course_form.html",
        course=course,
        LEVELS=LEVELS,
        is_pro=current_user.is_pro,
        recommended=recommended_questions(None),
    ), status


def _render_course(course):
    is_owner = current_user.is_authenticated and course.company_id == current_user.id
    enrollment = None
    if current_user.is_authenticated and current_user.is_person:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, course_id=course.id
        ).first()
    invite_url = None
    if is_owner and course.is_private:
        invite_url = url_for("courses.private", token=course.invite_token, _external=True)
    return render_template(
        "course.html",
        course=course,
        lessons=course.lessons,
        enrollment=enrollment,
        is_owner=is_owner,
        invite_url=invite_url,
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
        _apply_plan_rules(data)
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
        _apply_plan_rules(data)
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
    if course is None or not course_visible_to(course, current_user):
        abort(404)
    return _render_course(course)


@bp.route("/course/private/<token>")
def private(token):
    course = Course.query.filter_by(invite_token=token).first()
    if course is None:
        abort(404)
    return _render_course(course)


# ---------- learning ----------

@bp.route("/course/<int:course_id>/start", methods=["POST"])
@login_required
def start(course_id):
    if not current_user.is_person:
        abort(403)
    course = db.session.get(Course, course_id)
    if course is None or not course_visible_to(course, current_user):
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
    courses = (
        Course.query.filter_by(company_id=company.id, is_private=False, status="published")
        .order_by(Course.created_at.desc())
        .all()
    )
    return render_template("company.html", company=company, courses=courses)


@bp.route("/api/search")
def search():
    q = request.args.get("q", "").strip()
    by = request.args.get("by", "topic")
    return jsonify(search_companies(q, by))