import io

import pytest

from database import db
from database.models import Course, Lesson, User


def company_client(app, email="hr@acme.md", name="Acme"):
    client = app.test_client()
    client.post("/signup", data={"type": "company", "company_name": name, "email": email})
    return client


def person_client(app, email="ion@test.md"):
    client = app.test_client()
    client.post("/signup", data={"type": "person", "first_name": "Ion", "last_name": "Popescu", "email": email})
    return client


def create_course(client, level="beginner", knowledge_type="procedure", duration=3):
    response = client.post("/course/new", data={
        "title": "Rebar check", "description": "d", "topic": "Concrete", "profession": "Builder",
        "outcome": "Check rebar", "level": level, "knowledge_type": knowledge_type,
        "duration": str(duration), "visibility": "public",
    })
    assert response.status_code == 302
    assert "/builder" in response.headers["Location"]
    return Course.query.order_by(Course.id.desc()).first()


def media_question_ids(app, course):
    from core.course_builder import select_questions
    with app.app_context():
        course = db.session.get(Course, course.id)
        return [q["id"] for q in select_questions(course.level, course.knowledge_type,
                                                    course.duration, course.yes_answer_ids)
                if q["answer_type"] == "media"]


def test_builder_shows_questions(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    page = client.get(f"/course/{course.id}/builder")
    assert page.status_code == 200
    assert b"What should the learner be able to do" in page.data
    assert b"0 of 5" in page.data


def test_builder_only_for_owner(app):
    owner = company_client(app)
    with app.app_context():
        course = create_course(owner)
    assert person_client(app).get(f"/course/{course.id}/builder").status_code == 403
    other = company_client(app, email="hr@other.md", name="Other")
    assert other.get(f"/course/{course.id}/builder").status_code == 403
    assert owner.get("/course/999/builder").status_code == 404


def test_text_answer_becomes_lesson(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    first, second = media_question_ids(app, course)[:2]

    # answer the second question first: lessons must still follow the script order
    client.post(f"/course/{course.id}/builder/{second}", data={"title": "Show it", "text": "Step 1"})
    client.post(f"/course/{course.id}/builder/{first}", data={"title": "Goal", "text": "You will..."})

    with app.app_context():
        lessons = Lesson.query.filter_by(course_id=course.id).order_by(Lesson.order).all()
        assert [(l.order, l.question_id, l.title) for l in lessons] == [
            (1, first, "Goal"), (2, second, "Show it")]

    assert b"2 of 5" in client.get(f"/course/{course.id}/builder").data


def test_empty_answer_is_rejected(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    first = media_question_ids(app, course)[0]
    client.post(f"/course/{course.id}/builder/{first}", data={"title": "Goal", "text": ""})
    with app.app_context():
        assert Lesson.query.count() == 0


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


def test_video_answer_and_replacement(app, fake_storage):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    first = media_question_ids(app, course)[0]

    client.post(f"/course/{course.id}/builder/{first}", data={
        "title": "Goal", "video": (io.BytesIO(b"fake video"), "goal.mp4")},
        content_type="multipart/form-data")
    with app.app_context():
        old_name = Lesson.query.one().video_filename
    assert old_name in fake_storage

    client.post(f"/course/{course.id}/builder/{first}", data={
        "title": "Goal", "video": (io.BytesIO(b"new video"), "goal2.webm")},
        content_type="multipart/form-data")
    with app.app_context():
        new_name = Lesson.query.one().video_filename
    assert new_name != old_name
    assert new_name in fake_storage
    assert old_name not in fake_storage


def test_wrong_video_format(app, fake_storage):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    first = media_question_ids(app, course)[0]
    response = client.post(f"/course/{course.id}/builder/{first}", data={
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
    first = media_question_ids(app, course)[0]
    response = client.post(f"/course/{course.id}/builder/{first}", data={
        "title": "Goal", "video": (io.BytesIO(b"x"), "goal.mp4")},
        content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"not configured" in response.data


def test_question_not_in_script(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client)
    assert client.post(f"/course/{course.id}/builder/99999", data={"text": "x"}).status_code == 404


def test_yes_adds_follow_up_questions(app):
    client = company_client(app)
    with app.app_context():
        course = create_course(client, level="intermediate", knowledge_type="procedure", duration=15)
    assert b"Show one situation where the usual method does not work" not in \
        client.get(f"/course/{course.id}/builder").data

    client.post(f"/course/{course.id}/builder/36", data={"yes_no": "yes"})
    with app.app_context():
        assert 36 in db.session.get(Course, course.id).yes_answer_ids
    assert b"Show one situation where the usual method does not work" in \
        client.get(f"/course/{course.id}/builder").data

    client.post(f"/course/{course.id}/builder/36", data={"yes_no": "no"})
    with app.app_context():
        assert 36 not in db.session.get(Course, course.id).yes_answer_ids


def make_lesson(app, client):
    with app.app_context():
        course = create_course(client)
    first = media_question_ids(app, course)[0]
    client.post(f"/course/{course.id}/builder/{first}", data={"title": "Goal", "text": "t"})
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
