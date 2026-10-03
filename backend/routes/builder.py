"""Course studio for the master.

The master builds the course lesson by lesson. A lesson = title + video and/or text.
Next to the lesson list the page shows recommended questions (core/questions.py)
for the course level; a question can be attached to a lesson with the "Use" button
(then the lesson keeps its question_id). Time is only a hint and is never checked.

    builder.script         GET  /course/<id>/builder
    builder.add_lesson     POST /course/<id>/lessons
    builder.edit_lesson    POST /course/<id>/lessons/<lesson_id>
    builder.delete_lesson  POST /course/<id>/lessons/<lesson_id>/delete
    builder.quiz_edit      GET/POST /course/<id>/lesson/<lesson_id>/quiz/edit
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from backend.uploads import delete_video, save_video
from core.course_builder import recommended_questions
from core.questions import QUESTIONS, QUIZ_TEMPLATES
from database import db
from database.models import Course, Lesson, Quiz, QuizAnswer, QuizQuestion

bp = Blueprint("builder", __name__)

# Only questions that are answered with a video/text can be attached to a lesson
MEDIA_QUESTION_IDS = {q["id"] for q in QUESTIONS if q["answer_type"] == "media"}
QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}


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


def _read_question_id(course, current_lesson=None):
    """question_id from the form. Returns (question_id, error).
    Empty -> (None, None). A question can be used by one lesson of the course only."""
    raw = request.form.get("question_id", "").strip()
    if not raw:
        return None, None
    try:
        question_id = int(raw)
    except ValueError:
        return None, "Unknown question."
    if question_id not in MEDIA_QUESTION_IDS:
        return None, "Unknown question."
    taken = Lesson.query.filter_by(course_id=course.id, question_id=question_id).first()
    if taken is not None and taken is not current_lesson:
        return None, "This question is already used by another lesson."
    return question_id, None


def _read_video():
    """Uploaded video file or None."""
    video = request.files.get("video")
    return video if video is not None and video.filename else None


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
        used_question_ids={l.question_id for l in lessons if l.question_id is not None},
        is_pro=current_user.is_pro,
    )


# ---------- add / edit / delete a lesson ----------

@bp.route("/course/<int:course_id>/lessons", methods=["POST"])
@login_required
def add_lesson(course_id):
    course = _owned_course_or_abort(course_id)

    title = request.form.get("title", "").strip()[:200]
    text = request.form.get("text", "").strip()
    if not title:
        flash("Enter the lesson title.", "error")
        return _back_to_script(course)

    question_id, error = _read_question_id(course)
    if error:
        flash(error, "error")
        return _back_to_script(course)

    filename = None
    video = _read_video()
    if video is not None:
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
        question_id=question_id,
        video_filename=filename,
    )
    db.session.add(lesson)
    db.session.flush()
    _renumber_lessons(course)
    db.session.commit()
    flash(f"Lesson {lesson.order} added. Now add a quick quiz to it.", "success")
    return _back_to_script(course, lesson)


@bp.route("/course/<int:course_id>/lessons/<int:lesson_id>", methods=["POST"])
@login_required
def edit_lesson(course_id, lesson_id):
    course = _owned_course_or_abort(course_id)
    lesson = _lesson_or_abort(course, lesson_id)

    title = request.form.get("title", "").strip()[:200]
    text = request.form.get("text", "").strip()
    if not title:
        flash("Enter the lesson title.", "error")
        return _back_to_script(course, lesson)

    question_id, error = _read_question_id(course, current_lesson=lesson)
    if error:
        flash(error, "error")
        return _back_to_script(course, lesson)

    new_filename = None
    video = _read_video()
    if video is not None:
        try:
            new_filename = save_video(video)
        except (ValueError, RuntimeError) as error:
            flash(str(error), "error")
            return _back_to_script(course, lesson)

    lesson.title = title
    lesson.text = text or None
    lesson.question_id = question_id
    old_filename = None
    if new_filename:
        old_filename = lesson.video_filename
        lesson.video_filename = new_filename
    db.session.commit()

    # the old video is removed only after the new one is really saved in the database
    if old_filename:
        delete_video(old_filename)
    flash("Lesson saved.", "success")
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
    flash("Lesson deleted.", "info")
    return _back_to_script(course)


# ---------- quiz for one lesson ----------

@bp.route("/course/<int:course_id>/lesson/<int:lesson_id>/quiz/edit", methods=["GET", "POST"])
@login_required
def quiz_edit(course_id, lesson_id):
    course = _owned_course_or_abort(course_id)
    lesson = db.session.get(Lesson, lesson_id)
    if lesson is None or lesson.course_id != course.id:
        abort(404)

    question = QUESTIONS_BY_ID.get(lesson.question_id)
    category = question["category"] if question else None

    if request.method == "POST":
        error = _add_quiz_question(lesson, category)
        if error:
            flash(error, "error")
        else:
            db.session.commit()
            flash("Question added.", "success")
        return redirect(url_for("builder.quiz_edit", course_id=course.id, lesson_id=lesson.id))

    return render_template(
        "quiz_edit.html",
        course=course,
        lesson=lesson,
        quiz=lesson.quiz,
        suggestions=QUIZ_TEMPLATES.get(category, []),
    )


def _add_quiz_question(lesson, category):
    """Reads the form and adds one question to the lesson quiz. Returns an error text or None."""
    form = request.form
    text = form.get("text", "").strip()
    if not text:
        return "Enter the question."

    answers = {n: form.get(f"answer_{n}", "").strip() for n in range(1, 5)}
    filled = {n: a for n, a in answers.items() if a}
    if len(filled) < 2:
        return "Add at least two answers."

    correct = form.get("correct", type=int)
    if correct not in filled:
        return "Mark which filled-in answer is correct."

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