import io

import pytest

from tests.conftest import signup_confirmed
from database import db
from database.models import Course, Lesson


def company_client(app, email="hr@acme.md", name="Acme"):
    client = app.test_client()
    signup_confirmed(client, {"type": "company", "company_name": name, "email": email})
    return client


def person_client(app, email="ion@test.md"):
    client = app.test_client()
    signup_confirmed(client, {"type": "person", "first_name": "Ion", "last_name": "Popescu", "email": email})
    return client


def create_course(client, level="beginner", visibility="public"):
    response = client.post("/course/new", data={
        "title": "Rebar check", "description": "d", "topic": "Concrete", "profession": "Builder",
        "outcome": "Check rebar", "level": level, "visibility": visibility,
    })
    assert response.status_code == 302
    assert "/builder" in response.headers["Location"]
    return Course.query.order_by(Course.id.desc()).first()


def add_lesson(client, course, title="Goal", text="t", **extra):
    return client.post(f"/course/{course.id}/lessons", data={"title": title, "text": text, **extra})


def test_builder_page_opens(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    assert client.get(f"/course/{course.id}/builder").status_code == 200


def test_builder_only_for_owner(app):
    owner = company_client(app)
    with app.app_context():
        course = create_course(owner)
    assert person_client(app).get(f"/course/{course.id}/builder").status_code == 403
    other = company_client(app, email="hr@other.md", name="Other")
    assert other.get(f"/course/{course.id}/builder").status_code == 403
    assert other.post(f"/course/{course.id}/lessons", data={"title": "x"}).status_code == 403
    assert owner.get("/course/999/builder").status_code == 404


def test_add_lessons_are_numbered_in_order(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    response = add_lesson(client, course, "First")
    assert response.status_code == 302
    assert "#lesson-" in response.headers["Location"]
    add_lesson(client, course, "Second")
    with app.app_context():
        lessons = Lesson.query.filter_by(course_id=course.id).order_by(Lesson.order).all()
        assert [(l.order, l.title) for l in lessons] == [(1, "First"), (2, "Second")]


def test_lesson_without_title_is_rejected(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    add_lesson(client, course, title="  ")
    with app.app_context():
        assert Lesson.query.count() == 0


def test_lesson_with_recommended_question(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    add_lesson(client, course, "Goal", question_id="1")
    with app.app_context():
        assert Lesson.query.one().question_id == 1
    # the same question cannot be used twice in one course
    add_lesson(client, course, "Goal again", question_id="1")
    # unknown question id
    add_lesson(client, course, "Weird", question_id="99999")
    with app.app_context():
        assert Lesson.query.count() == 1


def test_edit_lesson(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    add_lesson(client, course, "Old", text="old text")
    with app.app_context():
        lesson_id = Lesson.query.one().id
    response = client.post(f"/course/{course.id}/lessons/{lesson_id}",
                           data={"title": "New", "text": "new text", "question_id": "1"})
    assert response.status_code == 302
    with app.app_context():
        lesson = db.session.get(Lesson, lesson_id)
        assert (lesson.title, lesson.text, lesson.question_id) == ("New", "new text", 1)
    # a lesson of another course cannot be edited through this course
    other = company_client(app, email="hr@other.md", name="Other")
    with app.app_context():
        other_course = create_course(other)
    assert other.post(f"/course/{other_course.id}/lessons/{lesson_id}", data={"title": "x"}).status_code == 404


def test_delete_lesson_renumbers(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    for title in ("A", "B", "C"):
        add_lesson(client, course, title)
    with app.app_context():
        middle = Lesson.query.filter_by(title="B").one().id
    response = client.post(f"/course/{course.id}/lessons/{middle}/delete")
    assert response.status_code == 302
    assert "#" not in response.headers["Location"]
    with app.app_context():
        lessons = Lesson.query.filter_by(course_id=course.id).order_by(Lesson.order).all()
        assert [(l.order, l.title) for l in lessons] == [(1, "A"), (2, "C")]


@pytest.fixture
def fake_storage(monkeypatch):
    """Video storage is replaced by a dict, so the test works with local files and Cloudinary alike."""
    stored = {}

    def save(file_storage):
        from backend.uploads import ALLOWED_EXTENSIONS
        if file_storage.filename.rsplit(".", 1)[-1].lower() not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported video format.")
        name = f"video-{len(stored) + 1}"
        stored[name] = file_storage.read()
        return name

    def delete(name):
        return stored.pop(name, None) is not None

    monkeypatch.setattr("backend.routes.builder.save_video", save)
    monkeypatch.setattr("backend.routes.builder.delete_video", delete)
    return stored


def test_video_replacement_and_delete(app, fake_storage):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    client.post(f"/course/{course.id}/lessons", data={
        "title": "Goal", "video": (io.BytesIO(b"fake video"), "goal.mp4")},
        content_type="multipart/form-data")
    with app.app_context():
        lesson = Lesson.query.one()
        lesson_id, old_name = lesson.id, lesson.video_filename
    assert old_name in fake_storage

    # empty video field keeps the old video
    client.post(f"/course/{course.id}/lessons/{lesson_id}", data={"title": "Goal 2"})
    with app.app_context():
        assert db.session.get(Lesson, lesson_id).video_filename == old_name

    # a new video replaces the old one
    client.post(f"/course/{course.id}/lessons/{lesson_id}", data={
        "title": "Goal 2", "video": (io.BytesIO(b"new video"), "goal2.webm")},
        content_type="multipart/form-data")
    with app.app_context():
        new_name = db.session.get(Lesson, lesson_id).video_filename
    assert new_name != old_name
    assert new_name in fake_storage and old_name not in fake_storage

    # deleting the lesson removes its video
    client.post(f"/course/{course.id}/lessons/{lesson_id}/delete")
    assert new_name not in fake_storage


def test_wrong_video_format(app, fake_storage):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    response = client.post(f"/course/{course.id}/lessons", data={
        "title": "Goal", "video": (io.BytesIO(b"x"), "virus.exe")},
        content_type="multipart/form-data", follow_redirects=True)
    assert b"Unsupported video format" in response.data
    with app.app_context():
        assert Lesson.query.count() == 0


def test_storage_not_configured(app, monkeypatch):
    def broken(file_storage):
        raise RuntimeError("Video storage is not configured.")
    monkeypatch.setattr("backend.routes.builder.save_video", broken)
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    response = client.post(f"/course/{course.id}/lessons", data={
        "title": "Goal", "video": (io.BytesIO(b"x"), "goal.mp4")},
        content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"not configured" in response.data


def make_lesson(app, client):
    with app.app_context():
        course = create_course(client)
    add_lesson(client, course, "Goal", question_id="1")
    with app.app_context():
        return course, Lesson.query.one()


def test_quiz_edit_page(app):
    client = company_client(app)
    course, lesson = make_lesson(app, client)
    page = client.get(f"/course/{course.id}/lesson/{lesson.id}/quiz/edit")
    assert page.status_code == 200
    assert b"What should you be able to do after watching this video?" in page.data  # suggestion


def test_add_quiz_question(app):
    client = company_client(app)
    course, lesson = make_lesson(app, client)
    client.post(f"/course/{course.id}/lesson/{lesson.id}/quiz/edit", data={
        "pass_score": "80", "text": "What is checked first?",
        "answer_1": "Spacing", "answer_2": "Color", "answer_3": "", "answer_4": "", "correct": "1"})
    with app.app_context():
        quiz = db.session.get(Lesson, lesson.id).quiz
        assert quiz.pass_score == 80
        assert len(quiz.questions) == 1
        question = quiz.questions[0]
        assert question.category == "goal"
        assert [(a.text, a.is_correct) for a in question.answers] == [("Spacing", True), ("Color", False)]


def test_bad_quiz_question_is_rejected(app):
    client = company_client(app)
    course, lesson = make_lesson(app, client)
    url = f"/course/{course.id}/lesson/{lesson.id}/quiz/edit"
    client.post(url, data={"text": "Q", "answer_1": "Only one", "correct": "1"})
    client.post(url, data={"text": "Q", "answer_1": "A", "answer_2": "B", "correct": "3"})
    with app.app_context():
        assert db.session.get(Lesson, lesson.id).quiz is None


def test_quiz_edit_other_course_lesson(app):
    client = company_client(app)
    course, lesson = make_lesson(app, client)
    other = company_client(app, email="hr@other.md", name="Other")
    assert other.get(f"/course/{course.id}/lesson/{lesson.id}/quiz/edit").status_code == 403


# ---------- private courses (Per course and Monthly plans only, see tests/test_plans.py) ----------

def buy_monthly(client):
    """Private courses and several courses need a paid plan."""
    client.post("/pricing/choose", data={"plan": "monthly"})


def edit_course(client, course, visibility):
    return client.post(f"/course/{course.id}/edit", data={
        "title": "Rebar check", "description": "d", "topic": "Concrete", "profession": "Builder",
        "outcome": "Check rebar", "level": "beginner", "visibility": visibility,
    })


def test_company_creates_private_course(app):
    client = company_client(app)
    buy_monthly(client)
    with app.app_context():
        course = create_course(client, visibility="private")
        assert course.is_private is True
        assert course.invite_token  # the invite link is created as before


def test_unknown_visibility_becomes_public(app):
    client = company_client(app)
    buy_monthly(client)
    with app.app_context():
        assert create_course(client, visibility="secret").is_private is False
        assert create_course(client, visibility="").is_private is False


def test_edit_keeps_private_and_can_switch(app):
    client = company_client(app)
    buy_monthly(client)
    with app.app_context():
        course = create_course(client, visibility="private")
        course_id, token = course.id, course.invite_token

    assert edit_course(client, course, "private").status_code == 302
    with app.app_context():
        course = db.session.get(Course, course_id)
        assert course.is_private is True and course.invite_token == token

    edit_course(client, course, "public")
    with app.app_context():
        assert db.session.get(Course, course_id).is_private is False

    edit_course(client, course, "private")
    with app.app_context():
        assert db.session.get(Course, course_id).is_private is True


def test_private_course_stays_private_after_publish(app):
    # Another company has a public course on the same topic (control: search itself works).
    other = company_client(app, email="hr@other.md", name="Other")
    with app.app_context():
        public_course = create_course(other)
    other.post(f"/course/{public_course.id}/publish")

    client = company_client(app)
    buy_monthly(client)
    with app.app_context():
        course = create_course(client, visibility="private")
        course_id, token = course.id, course.invite_token
    assert client.post(f"/course/{course_id}/publish").status_code == 302

    # found in search and on the company page, but a stranger can only send a request
    guest = app.test_client()
    names = [c["company_name"] for c in guest.get("/api/search?q=Concrete&by=topic").get_json()]
    assert "Other" in names and "Acme" in names
    with app.app_context():
        company_id = db.session.get(Course, course_id).company_id
    assert b"By request" in guest.get(f"/company/{company_id}").data
    assert b"request access" in guest.get(f"/course/{course_id}").data

    # but it opens with the invite link, and the owner finds that link in the account
    assert guest.get(f"/course/private/{token}").status_code == 200
    assert guest.get("/course/private/wrong-token").status_code == 404
    assert f"/course/private/{token}".encode() in client.get("/account").data


def test_pro_page_is_gone(app):
    client = company_client(app)
    assert client.get("/pro").status_code == 404
    assert client.post("/pro", data={"next": "/course/new"}).status_code == 404