"""
Frontend preview: shows our real templates (frontend/templates) with fake data.
No database and no backend needed.

Run from the project root:
    python frontend/preview/preview_app.py
Open http://127.0.0.1:5001

The URLs and endpoint names are the same as in the team contract
(courses.view, quiz.submit, builder.script ...), so url_for() in templates works
here exactly like in the real app.
"""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from flask import (Blueprint, Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from jinja2 import ChoiceLoader, FileSystemLoader

import fake_data as fake

PREVIEW_FOLDER = Path(__file__).resolve().parent
FRONTEND_FOLDER = PREVIEW_FOLDER.parent

app = Flask(__name__, static_folder=str(FRONTEND_FOLDER / "static"), static_url_path="/static")
app.secret_key = "preview-only"

# Real templates first. If the team's base.html isn't in the folder yet, the stub one is used.
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(str(FRONTEND_FOLDER / "templates")),
    FileSystemLoader(str(PREVIEW_FOLDER / "stub_templates")),
])

state = fake.make_starting_state()


# ---------- Who is "logged in" (switch with the bar at the bottom of every page) ----------
ROLES = {"guest": fake.GuestUser(), "person": fake.ana, "company": fake.northwind}


def get_current_user():
    return ROLES.get(request.cookies.get("preview_role", "person"), fake.ana)


@app.context_processor
def add_template_helpers():
    return {"current_user": get_current_user(), "csrf_token": lambda: "preview-token"}


# ---------- Helpers ----------
def find_course(course_id):
    course = fake.ALL_COURSES.get(course_id)
    if course is None:
        abort(404)
    return course


def is_owner(course):
    user = get_current_user()
    return user.is_company and course.company.id == user.id


def get_enrollment(course):
    if not get_current_user().is_person:
        return None
    return state["enrollments"].get(course.id)


def require_enrollment(course, n):
    enrollment = get_enrollment(course)
    if enrollment is None:
        abort(403)
    if n < 1 or n > course.lesson_count:
        abort(404)
    if enrollment.status != "completed" and n > enrollment.current_lesson:
        abort(403)
    return enrollment


def invite_link(course):
    if course.is_private:
        return url_for("courses.private", token=course.invite_token, _external=True)
    return None


# =========================================================
# main
# =========================================================
main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("_preview_index.html", courses=list(fake.ALL_COURSES.values()))


@main.route("/explore")
def explore():
    return render_template("explore.html")


@main.route("/account")
def account():
    user = get_current_user()
    if not user.is_authenticated:
        flash("Please log in first.", "info")
        return redirect(url_for("main.home"))

    if user.is_person:
        enrollments = list(state["enrollments"].values())
        stats = {"started": len(enrollments),
                 "completed": sum(1 for e in enrollments if e.status == "completed")}
        return render_template("account_person.html", user=user, enrollments=enrollments,
                               stats=stats, offers=state["offers"])

    company_courses = [course for course in fake.ALL_COURSES.values() if course.company.id == user.id]
    courses = [{"course": course, "enrolled": 12 if course.status == "published" else 0,
                "completed": 4 if course.status == "published" else 0, "invite_url": invite_link(course)}
               for course in company_courses]
    return render_template("account_company.html", user=user, courses=courses,
                           candidates=state["candidates"])


# =========================================================
# auth (fake: just switches the preview role)
# =========================================================
auth = Blueprint("auth", __name__)


def switch_role_and_go_back(role):
    response = redirect(request.referrer or url_for("main.home"))
    response.set_cookie("preview_role", role)
    return response


@auth.route("/signup", methods=["POST"])
def signup():
    flash("Welcome! (preview: you are now logged in)", "success")
    return switch_role_and_go_back("company" if request.form.get("type") == "company" else "person")


@auth.route("/login", methods=["POST"])
def login():
    flash("Preview: no email is sent, you are logged in as the demo person.", "info")
    return switch_role_and_go_back("person")


@auth.route("/login/<token>")
def magic_login(token):
    return switch_role_and_go_back("person")


@auth.route("/logout", methods=["POST"])
def logout():
    return switch_role_and_go_back("guest")


# =========================================================
# courses
# =========================================================
courses = Blueprint("courses", __name__)


@courses.route("/course/new", methods=["GET", "POST"])
def new():
    if not get_current_user().is_company:
        abort(403)
    if request.method == "POST":
        flash(f"Course “{request.form.get('title')}” created (preview — not saved).", "success")
        return redirect(url_for("builder.script", course_id=fake.latte_art.id))
    return render_template("course_form.html", course=None,
                           LEVELS=fake.LEVELS, TYPES=fake.TYPES, DURATIONS=fake.DURATIONS)


@courses.route("/course/<int:course_id>/edit", methods=["GET", "POST"])
def edit(course_id):
    course = find_course(course_id)
    if not is_owner(course):
        abort(403)
    if request.method == "POST":
        flash("Changes saved (preview — not really).", "success")
        return redirect(url_for("courses.view", course_id=course.id))
    return render_template("course_form.html", course=course,
                           LEVELS=fake.LEVELS, TYPES=fake.TYPES, DURATIONS=fake.DURATIONS)


@courses.route("/course/<int:course_id>/delete", methods=["POST"])
def delete(course_id):
    flash("Course deleted (preview — not really).", "success")
    return redirect(url_for("main.account"))


@courses.route("/course/<int:course_id>/publish", methods=["POST"])
def publish(course_id):
    course = find_course(course_id)
    course.status = "published"
    flash("Course published!", "success")
    return redirect(url_for("courses.view", course_id=course.id))


def render_course_page(course):
    return render_template("course.html", course=course, lessons=course.lessons,
                           enrollment=get_enrollment(course), is_owner=is_owner(course),
                           invite_url=invite_link(course) if is_owner(course) else None)


@courses.route("/course/<int:course_id>")
def view(course_id):
    return render_course_page(find_course(course_id))


@courses.route("/course/private/<token>")
def private(token):
    for course in fake.ALL_COURSES.values():
        if course.invite_token == token:
            return render_course_page(course)
    abort(404)


@courses.route("/course/<int:course_id>/start", methods=["POST"])
def start(course_id):
    course = find_course(course_id)
    user = get_current_user()
    if not user.is_person:
        abort(403)
    if course.id not in state["enrollments"]:
        state["enrollments"][course.id] = fake.make_enrollment(user, course, current_lesson=1, days_ago=0)
    return redirect(url_for("courses.lesson", course_id=course.id, n=1))


@courses.route("/course/<int:course_id>/lesson/<int:n>")
def lesson(course_id, n):
    course = find_course(course_id)
    enrollment = require_enrollment(course, n)
    current_lesson = course.lessons[n - 1]
    video_url = fake.DEMO_VIDEO if current_lesson.video_filename else None
    quiz_url = url_for("quiz.take", course_id=course.id, n=n) if current_lesson.quiz else None
    return render_template("lesson.html", course=course, lessons=course.lessons, lesson=current_lesson,
                           n=n, enrollment=enrollment, video_url=video_url, quiz_url=quiz_url)


@courses.route("/media/<path:filename>")
def media(filename):
    return redirect(fake.DEMO_VIDEO)


@courses.route("/company/<int:company_id>")
def company_profile(company_id):
    company = fake.ALL_USERS.get(company_id)
    if company is None or not company.is_company:
        abort(404)
    public_courses = [c for c in fake.ALL_COURSES.values()
                      if c.company.id == company_id and not c.is_private and c.status == "published"]
    return render_template("company.html", company=company, courses=public_courses)


@courses.route("/api/search")
def search():
    search_text = request.args.get("q", "").strip().lower()
    search_by = request.args.get("by", "topic")
    field_for_search = {"topic": lambda c: c.topic, "company": lambda c: c.company.display_name,
                        "profession": lambda c: c.profession, "result": lambda c: c.outcome}
    get_field = field_for_search.get(search_by, field_for_search["topic"])

    found = {}
    for course in fake.ALL_COURSES.values():
        if course.is_private or course.status != "published":
            continue
        if search_text in (get_field(course) or "").lower():
            found.setdefault(course.company.id, []).append(course)

    answer = [{"id": company_id, "name": fake.ALL_USERS[company_id].display_name,
               "description": fake.ALL_USERS[company_id].company.description,
               "course_count": len(found_courses),
               "url": url_for("courses.company_profile", company_id=company_id)}
              for company_id, found_courses in found.items()]
    return jsonify(answer)


# =========================================================
# quiz
# =========================================================
quiz = Blueprint("quiz", __name__)


@quiz.route("/course/<int:course_id>/lesson/<int:n>/quiz")
def take(course_id, n):
    course = find_course(course_id)
    require_enrollment(course, n)
    current_lesson = course.lessons[n - 1]
    if current_lesson.quiz is None:
        abort(404)
    return render_template("quiz.html", course=course, lesson=current_lesson, n=n,
                           quiz=current_lesson.quiz, questions=current_lesson.quiz.questions)


@quiz.route("/course/<int:course_id>/lesson/<int:n>/quiz", methods=["POST"])
def submit(course_id, n):
    course = find_course(course_id)
    enrollment = require_enrollment(course, n)
    current_lesson = course.lessons[n - 1]
    lesson_quiz = current_lesson.quiz

    results = []
    for question in lesson_quiz.questions:
        chosen_id = request.form.get(f"q_{question.id}", type=int)
        chosen = next((a for a in question.answers if a.id == chosen_id), None)
        correct = next(a for a in question.answers if a.is_correct)
        results.append({"question": question, "chosen": chosen, "correct": correct})

    right_count = sum(1 for r in results if r["chosen"] is not None and r["chosen"].is_correct)
    score = round(right_count * 100 / len(results))
    passed = score >= lesson_quiz.pass_score
    is_last_lesson = n == course.lesson_count

    if passed and enrollment.status != "completed":
        enrollment.current_lesson = max(enrollment.current_lesson, n + 1)
        if is_last_lesson:
            enrollment.status = "completed"
            enrollment.completed_at = datetime.now()
            print(f"[preview email] To {course.company.email}: {get_current_user().display_name} completed {course.title} ({score}%)")
    if passed and is_last_lesson:
        return render_template("completed.html", course=course)

    next_url = url_for("courses.lesson", course_id=course.id, n=n + 1) if passed else None
    return render_template("quiz_result.html", course=course, lesson=current_lesson, n=n,
                           score=score, pass_score=lesson_quiz.pass_score, passed=passed, results=results,
                           next_url=next_url,
                           rewatch_url=url_for("courses.lesson", course_id=course.id, n=n),
                           retry_url=url_for("quiz.take", course_id=course.id, n=n))


@quiz.route("/offer/<int:user_id>/<int:course_id>", methods=["POST"])
def send_offer(user_id, course_id):
    for candidate in state["candidates"]:
        if candidate["user"].id == user_id and candidate["course"].id == course_id:
            candidate["offer_sent"] = True
    flash("Offer sent! (preview — no email)", "success")
    return redirect(url_for("main.account"))


# =========================================================
# builder
# =========================================================
builder = Blueprint("builder", __name__)


def build_script(course):
    lessons_by_question = {l.question_id: l for l in course.lessons if l.question_id}
    script = []
    for question in fake.QUESTIONS:
        if question["only_after"] and question["only_after"] not in course.yes_answer_ids:
            continue
        script.append({"q": question, "category_label": fake.CATEGORIES[question["category"]],
                       "lesson": lessons_by_question.get(question["id"]), "position": len(script) + 1})
    return script


@builder.route("/course/<int:course_id>/builder")
def script(course_id):
    course = find_course(course_id)
    if not is_owner(course):
        abort(403)
    steps = build_script(course)
    answered = sum(1 for step in steps if step["lesson"] or step["q"]["id"] in course.yes_answer_ids)
    return render_template("builder.html", course=course, script=steps, answered=answered, total=len(steps))


@builder.route("/course/<int:course_id>/builder/<int:question_id>", methods=["POST"])
def answer(course_id, question_id):
    course = find_course(course_id)
    if request.form.get("yes_no"):
        yes_ids = course.yes_answer_ids
        if request.form["yes_no"] == "yes":
            yes_ids.add(question_id)
        else:
            yes_ids.discard(question_id)
        course.yes_answers = ",".join(str(i) for i in sorted(yes_ids))
    else:
        existing = next((l for l in course.lessons if l.question_id == question_id), None)
        uploaded_video = request.files.get("video")
        if existing:
            existing.title = request.form.get("title") or existing.title
            existing.text = request.form.get("text") or None
        else:
            course.lessons.append(fake.make_lesson(course.lesson_count + 1, request.form.get("title") or "Untitled",
                                                   question_id, request.form.get("text") or None,
                                                   video=bool(uploaded_video and uploaded_video.filename)))
        flash("Answer saved.", "success")
    return redirect(url_for("builder.script", course_id=course.id) + f"#q{question_id}")


@builder.route("/course/<int:course_id>/lesson/<int:lesson_id>/quiz/edit", methods=["GET", "POST"])
def quiz_edit(course_id, lesson_id):
    course = find_course(course_id)
    if not is_owner(course):
        abort(403)
    current_lesson = next((l for l in course.lessons if l.id == lesson_id), None)
    if current_lesson is None:
        abort(404)

    if request.method == "POST":
        if current_lesson.quiz is None:
            current_lesson.quiz = fake.make_quiz(70, [])
        current_lesson.quiz.pass_score = request.form.get("pass_score", 70, type=int)
        correct_number = request.form.get("correct", 1, type=int)
        answers = [SimpleNamespace(id=fake.new_id(), text=request.form[f"answer_{number}"], is_correct=(number == correct_number))
                   for number in range(1, 5) if request.form.get(f"answer_{number}")]
        current_lesson.quiz.questions.append(SimpleNamespace(id=fake.new_id(), text=request.form["text"],
                                                             category=None, answers=answers))
        flash("Question added.", "success")
        return redirect(url_for("builder.quiz_edit", course_id=course.id, lesson_id=lesson_id))

    question = next((q for q in fake.QUESTIONS if q["id"] == current_lesson.question_id), None)
    suggestions = fake.QUIZ_TEMPLATES.get(question["category"], []) if question else []
    return render_template("quiz_edit.html", course=course, lesson=current_lesson,
                           quiz=current_lesson.quiz, suggestions=suggestions)


# =========================================================
# preview-only helpers
# =========================================================
preview_tools = Blueprint("preview_tools", __name__, static_folder=str(PREVIEW_FOLDER / "stub_static"),
                          static_url_path="/_preview/static")


@preview_tools.route("/_preview/as/<role>")
def preview_as(role):
    return switch_role_and_go_back(role if role in ROLES else "person")


@preview_tools.route("/_preview/reset")
def preview_reset():
    global state
    state = fake.make_starting_state()
    flash("Preview data reset.", "info")
    return redirect(url_for("main.home"))


for blueprint in [main, auth, courses, quiz, builder, preview_tools]:
    app.register_blueprint(blueprint)


@app.errorhandler(403)
def forbidden(error):
    return render_template("_preview_error.html", code=403,
                           message="You don't have access to this page. Try another role in the preview bar."), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("_preview_error.html", code=404, message="This page doesn't exist."), 404


# Adds a small "Preview as: Guest / Person / Company" bar to the bottom of every page.
PREVIEW_BAR = """
<div style="position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:9999;display:flex;gap:4px;
            align-items:center;padding:6px;border-radius:999px;background:#1f2421;color:#fff;font:600 13px system-ui;
            box-shadow:0 6px 20px rgba(0,0,0,.25);max-width:calc(100vw - 16px);overflow-x:auto;white-space:nowrap">
  <a href="/" style="color:#fff;padding:6px 10px;text-decoration:none">☰ Screens</a>
  {links}
  <a href="/_preview/reset" style="color:#aaa;padding:6px 10px;text-decoration:none">↺</a>
</div>
"""


@app.after_request
def add_preview_bar(response):
    if response.mimetype != "text/html":
        return response
    current_role = request.cookies.get("preview_role", "person")
    links = "".join(
        f'<a href="/_preview/as/{role}" style="color:#fff;padding:6px 12px;border-radius:999px;text-decoration:none;'
        f'background:{"#2c6e5a" if role == current_role else "transparent"}">{role.title()}</a>'
        for role in ROLES)
    html = response.get_data(as_text=True).replace("</body>", PREVIEW_BAR.format(links=links) + "</body>")
    response.set_data(html)
    return response


if __name__ == "__main__":
    # host="0.0.0.0" lets you open the preview on your phone (same Wi-Fi): http://<your-computer-ip>:5001
    app.run(debug=True, port=5001, host="0.0.0.0")
