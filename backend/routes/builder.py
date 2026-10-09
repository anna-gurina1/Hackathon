"""Course studio for the master.

The master builds the course lesson by lesson. A lesson = title + video and/or text.
Next to the lesson list the page shows recommended questions (core/questions.py)
for the course level. They are only hints: the master can tick the ones already
answered in the course (AnsweredQuestion) — a personal note that nobody else sees
and that is not linked to any lesson. Time is only a hint and is never checked.

    builder.script           GET  /course/<id>/builder
    builder.add_lesson       POST /course/<id>/lessons
    builder.edit_lesson      POST /course/<id>/lessons/<lesson_id>
    builder.delete_lesson    POST /course/<id>/lessons/<lesson_id>/delete
    builder.toggle_answered  POST /course/<id>/questions/<question_id>/answered
    builder.quiz_edit        GET/POST /course/<id>/lesson/<lesson_id>/quiz/edit
"""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from backend.i18n import _
from backend.plans import can_add_video, video_limit, videos_used
from backend.uploads import delete_video, save_video
from core.course_builder import recommended_questions
from core.questions import QUESTIONS, QUIZ_TEMPLATES
from database import db
from database.models import AnsweredQuestion, Course, Lesson, Quiz, QuizAnswer, QuizQuestion

bp = Blueprint("builder", __name__)

QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}
# Quiz ideas for a lesson that is not linked to a studio question: the first idea of every topic
GENERAL_QUIZ_SUGGESTIONS = [ideas[0] for ideas in QUIZ_TEMPLATES.values() if ideas]


# ---------- helpers ----------

def _owned_course_or_abort(course_id):
    """Course of the current company. Person or someone else's course -> 403, none -> 404."""
    if not current_user.is_company:
        abort(403)
    course = db.session.get(Course, course_id)
    if course is None:
        abort(404)
    if course.company_id != current_user.id:
        abort(403)
    return course


def _lesson_or_abort(course, lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None or lesson.course_id != course.id:
        abort(404)
    return lesson


def _renumber_lessons(course):
    """Lesson order is 1, 2, 3, ... without gaps."""
    lessons = sorted(
        Lesson.query.filter_by(course_id=course.id).all(),
        key=lambda l: (l.order or 0, l.id),
    )
    for number, lesson in enumerate(lessons, start=1):
        lesson.order = number


def _back_to_script(course, lesson=None):
    anchor = f"#lesson-{lesson.id}" if lesson is not None else ""
    return redirect(url_for("builder.script", course_id=course.id) + anchor)


def _read_video():
    """Uploaded video file or None."""
    video = request.files.get("video")
    return video if video is not None and video.filename else None


def _video_limit_reached(course):
    """True (and an error message is flashed) when the plan allows no more videos in this course."""
    if can_add_video(course):
        return False
    flash(
        _("Your plan allows {count} videos per course. Upgrade to add more.", count=video_limit(course.company)),
        "error",
    )
    return True


# ---------- the studio page ----------

@bp.route("/course/<int:course_id>/builder")
@login_required
def script(course_id):
    course = _owned_course_or_abort(course_id)
    lessons = course.lessons
    return render_template(
        "builder.html",
        course=course,
        lessons=lessons,
        recommended=recommended_questions(course.level),
        answered_question_ids={note.question_id for note in course.answered_questions},
        video_limit=video_limit(current_user),
        videos_used=videos_used(course),
        can_add_video=can_add_video(course),
    )


# ---------- add / edit / delete a lesson ----------

@bp.route("/course/<int:course_id>/lessons", methods=["POST"])
@login_required
def add_lesson(course_id):
    course = _owned_course_or_abort(course_id)

    title = request.form.get("title", "").strip()[:200]
    text = request.form.get("text", "").strip()
    if not title:
        flash(_("Enter the lesson title."), "error")
        return _back_to_script(course)

    filename = None
    video = _read_video()
    if video is not None:
        if _video_limit_reached(course):
            return _back_to_script(course)
        try:
            filename = save_video(video)
        except (ValueError, RuntimeError) as error:  # RuntimeError: video storage is not configured
            flash(str(error), "error")
            return _back_to_script(course)

    lesson = Lesson(
        course_id=course.id,
        order=len(course.lessons) + 1,
        title=title,
        text=text or None,
        video_filename=filename,
    )
    db.session.add(lesson)
    db.session.flush()
    _renumber_lessons(course)
    db.session.commit()
    flash(_("Lesson {number} added. Now add a quick quiz to it.", number=lesson.order), "success")
    return _back_to_script(course, lesson)


@bp.route("/course/<int:course_id>/lessons/<int:lesson_id>", methods=["POST"])
@login_required
def edit_lesson(course_id, lesson_id):
    course = _owned_course_or_abort(course_id)
    lesson = _lesson_or_abort(course, lesson_id)

    title = request.form.get("title", "").strip()[:200]
    text = request.form.get("text", "").strip()
    if not title:
        flash(_("Enter the lesson title."), "error")
        return _back_to_script(course, lesson)

    new_filename = None
    video = _read_video()
    if video is not None:
        # replacing the video of a lesson that already has one does not add a new video
        if not lesson.video_filename and _video_limit_reached(course):
            return _back_to_script(course, lesson)
        try:
            new_filename = save_video(video)
        except (ValueError, RuntimeError) as error:
            flash(str(error), "error")
            return _back_to_script(course, lesson)

    lesson.title = title
    lesson.text = text or None
    old_filename = None
    if new_filename:
        old_filename = lesson.video_filename
        lesson.video_filename = new_filename
    db.session.commit()

    # the old video is removed only after the new one is really saved in the database
    if old_filename:
        delete_video(old_filename)
    flash(_("Lesson saved."), "success")
    return _back_to_script(course, lesson)


@bp.route("/course/<int:course_id>/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required
def delete_lesson(course_id, lesson_id):
    course = _owned_course_or_abort(course_id)
    lesson = _lesson_or_abort(course, lesson_id)

    video_id = lesson.video_filename
    db.session.delete(lesson)
    db.session.flush()
    _renumber_lessons(course)
    db.session.commit()

    if video_id:
        delete_video(video_id)
    flash(_("Lesson deleted."), "info")
    return _back_to_script(course)


# ---------- the master's notes "I have answered this question" ----------

@bp.route("/course/<int:course_id>/questions/<int:question_id>/answered", methods=["POST"])
@login_required
def toggle_answered(course_id, question_id):
    """Tick / untick a studio question. studio.js asks for JSON; without JavaScript the form
    sends the master back to the studio."""
    course = _owned_course_or_abort(course_id)
    if question_id not in QUESTIONS_BY_ID:
        abort(404)

    note = AnsweredQuestion.query.filter_by(course_id=course.id, question_id=question_id).first()
    if note is None:
        db.session.add(AnsweredQuestion(course_id=course.id, question_id=question_id))
        is_answered = True
    else:
        db.session.delete(note)
        is_answered = False
    db.session.commit()

    if request.accept_mimetypes.best == "application/json":
        return jsonify(answered=is_answered)
    return redirect(request.referrer or url_for("builder.script", course_id=course.id))


# ---------- quiz for one lesson ----------

@bp.route("/course/<int:course_id>/lesson/<int:lesson_id>/quiz/edit", methods=["GET", "POST"])
@login_required
def quiz_edit(course_id, lesson_id):
    course = _owned_course_or_abort(course_id)
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None or lesson.course_id != course.id:
        abort(404)

    # old lessons made with the "Use" button keep quiz ideas of their topic
    question = QUESTIONS_BY_ID.get(lesson.question_id)
    category = question["category"] if question else None

    if request.method == "POST":
        error = _add_quiz_question(lesson, category)
        if error:
            flash(error, "error")
        else:
            db.session.commit()
            flash(_("Question added."), "success")
        return redirect(url_for("builder.quiz_edit", course_id=course.id, lesson_id=lesson.id))

    return render_template(
        "quiz_edit.html",
        course=course,
        lesson=lesson,
        quiz=lesson.quiz,
        suggestions=QUIZ_TEMPLATES.get(category) or GENERAL_QUIZ_SUGGESTIONS,
    )


def _add_quiz_question(lesson, category):
    """Reads the form and adds one question to the lesson quiz. Returns an error text or None."""
    form = request.form
    text = form.get("text", "").strip()
    if not text:
        return _("Enter the question.")

    answers = {n: form.get(f"answer_{n}", "").strip() for n in range(1, 5)}
    filled = {n: a for n, a in answers.items() if a}
    if len(filled) < 2:
        return _("Add at least two answers.")

    correct = form.get("correct", type=int)
    if correct not in filled:
        return _("Mark which filled-in answer is correct.")

    pass_score = form.get("pass_score", type=int)
    if pass_score is None or not 1 <= pass_score <= 100:
        pass_score = 70

    quiz = lesson.quiz
    if quiz is None:
        quiz = Quiz(lesson=lesson)
        db.session.add(quiz)
    quiz.pass_score = pass_score

    new_question = QuizQuestion(quiz=quiz, text=text, category=category)
    db.session.add(new_question)
    for number, answer_text in filled.items():
        db.session.add(QuizAnswer(question=new_question, text=answer_text, is_correct=(number == correct)))
    return None