import logging
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from backend.email import send_email
from backend.i18n import _, use_language
from database import db
from database.models import Course, Enrollment, Offer, QuizAttempt, User

bp = Blueprint("quiz", __name__)

log = logging.getLogger(__name__)


# ---------- helpers ----------

def _load_quiz_context(course_id, n):
    """Checks access and returns (course, enrollment, lesson, quiz).

    login_required is applied by the views. Rules:
    not a person -> 403, no course -> 404, not enrolled -> 403,
    n > current_lesson -> 403, no such lesson / no quiz / empty quiz -> 404.
    """
    if not current_user.is_person:
        abort(403)
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
    lesson = next((l for l in course.lessons if l.order == n), None)
    if lesson is None:
        abort(404)
    quiz = lesson.quiz
    if quiz is None or not quiz.questions:
        abort(404)
    return course, enrollment, lesson, quiz


# ---------- take / submit ----------

@bp.route("/course/<int:course_id>/lesson/<int:n>/quiz")
@login_required
def take(course_id, n):
    course, _enrollment, lesson, quiz = _load_quiz_context(course_id, n)
    return render_template(
        "quiz.html",
        course=course,
        lesson=lesson,
        n=n,
        quiz=quiz,
        questions=quiz.questions,
    )


@bp.route("/course/<int:course_id>/lesson/<int:n>/quiz", methods=["POST"])
@login_required
def submit(course_id, n):
    course, enrollment, lesson, quiz = _load_quiz_context(course_id, n)

    # Check the answers on the server
    results = []
    correct_count = 0
    for question in quiz.questions:
        raw = request.form.get(f"q_{question.id}", "")
        chosen = next((a for a in question.answers if str(a.id) == raw), None)
        right_answers = [a for a in question.answers if a.is_correct]
        is_right = chosen is not None and chosen.is_correct
        if is_right:
            correct_count += 1
            correct = chosen
        else:
            correct = right_answers[0] if right_answers else None
        results.append({"question": question, "chosen": chosen, "correct": correct})

    score = round(correct_count / len(quiz.questions) * 100)
    passed = score >= quiz.pass_score

    db.session.add(
        QuizAttempt(user_id=current_user.id, quiz_id=quiz.id, score=score, passed=passed)
    )

    just_completed = False
    if passed:
        # unlock the next lesson only when this was the furthest lesson
        if n == enrollment.current_lesson:
            enrollment.current_lesson = n + 1
        if n == course.lesson_count and enrollment.status != "completed":
            enrollment.status = "completed"
            enrollment.completed_at = datetime.utcnow()
            just_completed = True

    db.session.commit()

    if just_completed:
        # the progress is already saved, a mail failure must not break the page
        try:
            with use_language(course.company.language):  # in the company's language
                send_email(
                    course.company.email,
                    _("New candidate"),
                    _("{name} ({email}) has completed your course “{course}”.",
                      name=current_user.display_name, email=current_user.email, course=course.title)
                    + "\n" + _("Result of the last quiz: {score}%.", score=score) + "\n",
                )
        except Exception:  # noqa: BLE001
            log.exception("Could not send the completion email")

    if passed and n == course.lesson_count:
        return render_template("completed.html", course=course)

    return render_template(
        "quiz_result.html",
        course=course,
        lesson=lesson,
        n=n,
        score=score,
        pass_score=quiz.pass_score,
        passed=passed,
        results=results,
        next_url=url_for("courses.lesson", course_id=course.id, n=n + 1) if passed else None,
        rewatch_url=url_for("courses.lesson", course_id=course.id, n=n),
        retry_url=url_for("quiz.take", course_id=course.id, n=n),
    )


# ---------- job offer ----------

@bp.route("/offer/<int:user_id>/<int:course_id>", methods=["POST"])
@login_required
def send_offer(user_id, course_id):
    if not current_user.is_company:
        abort(403)
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    if course.company_id != current_user.id:
        abort(403)

    person = db.session.get(User, user_id)
    if person is None or not person.is_person:
        abort(404)
    finished = Enrollment.query.filter_by(
        user_id=person.id, course_id=course.id, status="completed"
    ).first()
    if finished is None:
        abort(404)

    text = request.form.get("text", "").strip()
    if not text:
        flash(_("Please write a message for the offer."), "error")
        return redirect(url_for("main.account"))

    db.session.add(
        Offer(company_id=current_user.id, user_id=person.id, course_id=course.id, text=text)
    )
    db.session.commit()

    with use_language(person.language):  # the subject is in the learner's language, the text is the company's own
        send_email(person.email, _("Job offer from {company}", company=current_user.display_name), text)
    flash(_("Offer sent to {name}.", name=person.display_name), "success")
    return redirect(url_for("main.account"))
