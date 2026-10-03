"""Course builder for the master.

The system picks interview questions (core/course_builder.py) by the course
level, knowledge type and duration. The master answers each question with a
video and/or text, and every answer becomes a lesson. Then the master adds a
short quiz to each lesson.

    builder.script     GET  /course/<id>/builder
    builder.answer     POST /course/<id>/builder/<question_id>
    builder.quiz_edit  GET/POST /course/<id>/lesson/<lesson_id>/quiz/edit
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from backend.uploads import delete_video, save_video
from core.course_builder import category_label, select_questions
from core.questions import QUESTIONS, QUIZ_TEMPLATES
from database import db
from database.models import Course, Lesson, Quiz, QuizAnswer, QuizQuestion

bp = Blueprint("builder", __name__)

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


def _script_for(course):
    """Questions for this course, in teaching order."""
    return select_questions(
        course.level, course.knowledge_type, course.duration, course.yes_answer_ids
    )


def _set_yes(course, question_id, said_yes):
    ids = course.yes_answer_ids
    if said_yes:
        ids.add(question_id)
    else:
        ids.discard(question_id)
    course.yes_answers = ",".join(str(i) for i in sorted(ids))


def _renumber_lessons(course):
    """Lesson order follows the question order in the script (1, 2, 3, ...).
    Lessons whose question is no longer in the script keep their place at the end."""
    position = {q["id"]: index for index, q in enumerate(_script_for(course))}
    lessons = sorted(
        Lesson.query.filter_by(course_id=course.id).all(),
        key=lambda l: (position.get(l.question_id, len(position)), l.order or 0, l.id),
    )
    for number, lesson in enumerate(lessons, start=1):
        lesson.order = number


# ---------- the script page ----------

@bp.route("/course/<int:course_id>/builder")
@login_required
def script(course_id):
    course = _owned_course_or_abort(course_id)
    lessons = {l.question_id: l for l in course.lessons if l.question_id is not None}

    items = []
    for position, question in enumerate(_script_for(course), start=1):
        items.append({
            "q": question,
            "category_label": category_label(question["category"]),
            "lesson": lessons.get(question["id"]),
            "position": position,
        })

    # Progress counts only questions that become lessons (yes/no questions are switches)
    media_items = [item for item in items if item["q"]["answer_type"] == "media"]
    answered = sum(1 for item in media_items if item["lesson"] is not None)

    return render_template(
        "builder.html",
        course=course,
        script=items,
        answered=answered,
        total=len(media_items),
    )


# ---------- saving one answer ----------

@bp.route("/course/<int:course_id>/builder/<int:question_id>", methods=["POST"])
@login_required
def answer(course_id, question_id):
    course = _owned_course_or_abort(course_id)
    question = QUESTIONS_BY_ID.get(question_id)
    if question is None or question_id not in {q["id"] for q in _script_for(course)}:
        abort(404)
    back = url_for("builder.script", course_id=course.id) + f"#q{question_id}"

    # yes/no: a switch that adds or removes follow-up questions
    if question["answer_type"] == "yes_no":
        value = request.form.get("yes_no")
        if value not in ("yes", "no"):
            flash("Choose Yes or No.", "error")
            return redirect(back)
        _set_yes(course, question_id, value == "yes")
        _renumber_lessons(course)
        db.session.commit()
        if value == "yes":
            flash("Follow-up questions were added to the script.", "success")
        return redirect(back)

    # media: the answer becomes a lesson
    lesson = Lesson.query.filter_by(course_id=course.id, question_id=question_id).first()
    title = request.form.get("title", "").strip()[:200] or question["text"][:200]
    text = request.form.get("text", "").strip()
    video = request.files.get("video")
    has_new_video = video is not None and bool(video.filename)

    if not has_new_video and not text and not (lesson and lesson.video_filename):
        flash("Add a video or a text answer.", "error")
        return redirect(back)

    new_filename = None
    if has_new_video:
        try:
            new_filename = save_video(video)
        except (ValueError, RuntimeError) as error:  # RuntimeError: video storage is not configured
            flash(str(error), "error")
            return redirect(back)

    if lesson is None:
        lesson = Lesson(course_id=course.id, question_id=question_id, order=0, title=title)
        db.session.add(lesson)

    lesson.title = title
    lesson.text = text or None
    if new_filename:
        if lesson.video_filename:
            delete_video(lesson.video_filename)
        lesson.video_filename = new_filename

    db.session.flush()
    _renumber_lessons(course)
    db.session.commit()
    flash(f"Saved as lesson {lesson.order}. Now add a quick quiz to it.", "success")
    return redirect(back)


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
