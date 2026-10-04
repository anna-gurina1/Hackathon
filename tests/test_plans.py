"""Tariff limits: courses, videos per course, private courses (backend/plans.py)."""
import importlib.util
import io
import itertools
import os
from contextlib import contextmanager

import pytest
from flask import template_rendered

from backend import plans
from database import db
from database.models import Course, Lesson, User
from tests.conftest import signup_confirmed


# ---------- helpers ----------

def company_client(app, email="hr@acme.md", name="Acme"):
    client = app.test_client()
    signup_confirmed(client, {"type": "company", "company_name": name, "email": email})
    return client


def person_client(app, email="ion@test.md"):
    client = app.test_client()
    signup_confirmed(client, {"type": "person", "first_name": "Ion", "last_name": "Popescu", "email": email})
    return client


def choose(client, plan):
    return client.post("/pricing/choose", data={"plan": plan})


def new_course(client, visibility="public", title="Rebar check"):
    return client.post("/course/new", data={
        "title": title, "description": "d", "topic": "Concrete", "profession": "Builder",
        "outcome": "Check rebar", "level": "beginner", "visibility": visibility,
    })


def course_count(app):
    with app.app_context():
        return Course.query.count()


def last_course_id(app):
    with app.app_context():
        return Course.query.order_by(Course.id.desc()).first().id


def video(name="clip.mp4"):
    return (io.BytesIO(b"fake video"), name)


def add_video_lesson(client, course_id, title="Lesson"):
    return client.post(
        f"/course/{course_id}/lessons",
        data={"title": title, "video": video()},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def videos_in(app, course_id):
    with app.app_context():
        return Lesson.query.filter(Lesson.course_id == course_id, Lesson.video_filename.isnot(None)).count()


@contextmanager
def captured_templates(app):
    """Names and variables of the templates rendered while the block runs."""
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template.name, dict(context)))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


@pytest.fixture
def fake_storage(monkeypatch):
    """Video storage is replaced by a dict, so the test works with local files and Cloudinary alike."""
    stored = {}
    counter = itertools.count(1)

    def save(file_storage):
        name = f"video-{next(counter)}"
        stored[name] = file_storage.read()
        return name

    def delete(name):
        return stored.pop(name, None) is not None

    monkeypatch.setattr("backend.routes.builder.save_video", save)
    monkeypatch.setattr("backend.routes.builder.delete_video", delete)
    monkeypatch.setattr("backend.routes.courses.delete_video", delete)
    return stored


# ---------- courses ----------

def test_free_company_cannot_create_a_second_course(app):
    client = company_client(app)
    assert new_course(client).status_code == 302
    assert course_count(app) == 1  # the first course is still a draft: drafts count too

    response = new_course(client, title="Second")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/pricing")
    assert course_count(app) == 1

    # the form page is closed as well
    response = client.get("/course/new")
    assert response.status_code == 302 and response.headers["Location"].endswith("/pricing")

    page = client.get("/pricing")
    assert b"You have used all courses on your plan" in page.data


def test_published_course_counts_too(app):
    client = company_client(app)
    new_course(client)
    client.post(f"/course/{last_course_id(app)}/publish")
    assert new_course(client).headers["Location"].endswith("/pricing")


def test_free_company_can_open_the_form_for_the_first_course(app):
    assert company_client(app).get("/course/new").status_code == 200


def test_deleting_a_course_frees_the_place(app, fake_storage):
    client = company_client(app)
    new_course(client)
    assert new_course(client).headers["Location"].endswith("/pricing")
    client.post(f"/course/{last_course_id(app)}/delete")
    assert new_course(client).headers["Location"].endswith("/builder")
    assert course_count(app) == 1


def test_per_course_gives_one_more_course_for_each_purchase(app):
    client = company_client(app)
    new_course(client)
    assert new_course(client).headers["Location"].endswith("/pricing")

    response = choose(client, "per_course")
    assert response.status_code == 302 and response.headers["Location"].endswith("/account")
    with app.app_context():
        company = User.query.filter_by(email="hr@acme.md").one().company
        assert (company.plan, company.course_credits) == ("per_course", 1)

    assert new_course(client, title="Second").headers["Location"].endswith("/builder")
    assert course_count(app) == 2
    assert new_course(client, title="Third").headers["Location"].endswith("/pricing")  # 1 + 1 = 2 courses

    choose(client, "per_course")  # buy one more
    assert new_course(client, title="Third").headers["Location"].endswith("/builder")
    assert course_count(app) == 3


def test_monthly_has_no_limits(app, fake_storage):
    client = company_client(app)
    choose(client, "monthly")
    for n in range(4):
        assert new_course(client, title=f"Course {n}").headers["Location"].endswith("/builder")
    course_id = last_course_id(app)
    for n in range(12):
        add_video_lesson(client, course_id, f"Lesson {n}")
    assert videos_in(app, course_id) == 12
    with app.app_context():
        user = User.query.filter_by(email="hr@acme.md").one()
        assert plans.course_limit(user) is None and plans.video_limit(user) is None


def test_switching_to_free_keeps_the_courses_but_blocks_new_ones(app):
    client = company_client(app)
    choose(client, "monthly")
    for n in range(3):
        new_course(client, title=f"Course {n}")
    choose(client, "free")
    assert course_count(app) == 3  # nothing is deleted
    assert new_course(client).headers["Location"].endswith("/pricing")


# ---------- videos in one course ----------

def test_free_fourth_video_is_not_saved(app, fake_storage):
    client = company_client(app)
    new_course(client)
    course_id = last_course_id(app)
    for n in range(3):
        add_video_lesson(client, course_id, f"Lesson {n}")
    assert videos_in(app, course_id) == 3

    response = add_video_lesson(client, course_id, "Lesson 4")
    assert b"Your plan allows 3 videos per course" in response.data
    assert videos_in(app, course_id) == 3
    assert len(fake_storage) == 3  # the file was not even uploaded


def test_free_text_lessons_do_not_use_videos(app, fake_storage):
    client = company_client(app)
    new_course(client)
    course_id = last_course_id(app)
    for n in range(5):
        client.post(f"/course/{course_id}/lessons", data={"title": f"Text {n}", "text": "only text"})
    for n in range(3):
        add_video_lesson(client, course_id, f"Video {n}")
    assert videos_in(app, course_id) == 3
    with app.app_context():
        assert Lesson.query.filter_by(course_id=course_id).count() == 8


def test_free_can_replace_the_video_of_a_lesson_at_the_limit(app, fake_storage):
    client = company_client(app)
    new_course(client)
    course_id = last_course_id(app)
    for n in range(3):
        add_video_lesson(client, course_id, f"Lesson {n}")
    with app.app_context():
        lesson = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.id).first()
        lesson_id, old_name = lesson.id, lesson.video_filename

    response = client.post(
        f"/course/{course_id}/lessons/{lesson_id}",
        data={"title": "Lesson 0", "video": video("new.webm")},
        content_type="multipart/form-data", follow_redirects=True,
    )
    assert b"Lesson saved" in response.data
    with app.app_context():
        new_name = db.session.get(Lesson, lesson_id).video_filename
    assert new_name != old_name and videos_in(app, course_id) == 3


def test_free_cannot_attach_a_first_video_to_a_lesson_over_the_limit(app, fake_storage):
    client = company_client(app)
    new_course(client)
    course_id = last_course_id(app)
    for n in range(3):
        add_video_lesson(client, course_id, f"Lesson {n}")
    client.post(f"/course/{course_id}/lessons", data={"title": "Only text", "text": "t"})
    with app.app_context():
        text_lesson_id = Lesson.query.filter_by(course_id=course_id, title="Only text").one().id

    response = client.post(
        f"/course/{course_id}/lessons/{text_lesson_id}",
        data={"title": "Only text", "video": video()},
        content_type="multipart/form-data", follow_redirects=True,
    )
    assert b"Your plan allows 3 videos per course" in response.data
    assert videos_in(app, course_id) == 3
    with app.app_context():
        assert db.session.get(Lesson, text_lesson_id).video_filename is None


def test_per_course_allows_ten_videos(app, fake_storage):
    client = company_client(app)
    choose(client, "per_course")
    new_course(client)
    course_id = last_course_id(app)
    for n in range(10):
        add_video_lesson(client, course_id, f"Lesson {n}")
    assert videos_in(app, course_id) == 10
    response = add_video_lesson(client, course_id, "Lesson 11")
    assert b"Your plan allows 10 videos per course" in response.data
    assert videos_in(app, course_id) == 10


def test_video_limit_is_per_course(app, fake_storage):
    client = company_client(app)
    choose(client, "per_course")
    new_course(client)
    first = last_course_id(app)
    new_course(client, title="Other")
    second = last_course_id(app)
    for n in range(3):
        add_video_lesson(client, first, f"A{n}")
        add_video_lesson(client, second, f"B{n}")
    assert videos_in(app, first) == 3 and videos_in(app, second) == 3


# ---------- the demo payment ----------

def test_person_cannot_choose_a_plan(app):
    client = person_client(app)
    assert choose(client, "monthly").status_code == 403


def test_guest_cannot_choose_a_plan(app):
    client = app.test_client()
    response = choose(client, "monthly")
    assert response.status_code == 302 and "/pricing" not in response.headers["Location"]


def test_unknown_plan_is_rejected(app):
    client = company_client(app)
    assert choose(client, "gold").status_code == 400
    assert client.post("/pricing/choose", data={}).status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="hr@acme.md").one().company.plan == "free"


def test_choose_plan_shows_a_message(app):
    client = company_client(app)
    page = client.post("/pricing/choose", data={"plan": "monthly"}, follow_redirects=True)
    assert b"Plan updated: Monthly." in page.data


# ---------- private courses ----------

def is_private(app, course_id):
    with app.app_context():
        return db.session.get(Course, course_id).is_private


def test_free_cannot_make_a_private_course(app):
    client = company_client(app)
    new_course(client, visibility="private")
    assert is_private(app, last_course_id(app)) is False
    page = client.get(f"/course/{last_course_id(app)}/builder")  # the message is shown on the next page
    assert b"Private courses are a Pro feature" in page.data


def test_free_cannot_switch_a_course_to_private_when_editing(app):
    client = company_client(app)
    new_course(client)
    course_id = last_course_id(app)
    client.post(f"/course/{course_id}/edit", data={
        "title": "Rebar check", "level": "beginner", "visibility": "private"})
    assert is_private(app, course_id) is False


@pytest.mark.parametrize("plan", ["per_course", "monthly"])
def test_paid_plans_can_make_private_courses(app, plan):
    client = company_client(app)
    choose(client, plan)
    new_course(client, visibility="private")
    course_id = last_course_id(app)
    assert is_private(app, course_id) is True
    client.post(f"/course/{course_id}/edit", data={
        "title": "Rebar check", "level": "beginner", "visibility": "public"})
    assert is_private(app, course_id) is False
    client.post(f"/course/{course_id}/edit", data={
        "title": "Rebar check", "level": "beginner", "visibility": "private"})
    assert is_private(app, course_id) is True


# ---------- variables for the templates ----------

def test_pricing_page_gets_current_plan(app):
    with captured_templates(app) as rendered:
        app.test_client().get("/pricing")
        person_client(app).get("/pricing")
    assert [ctx["current_plan"] for name, ctx in rendered if name == "pricing.html"] == [None, None]

    client = company_client(app)
    with captured_templates(app) as rendered:
        client.get("/pricing")
        choose(client, "monthly")
        client.get("/pricing")
    assert [ctx["current_plan"] for name, ctx in rendered if name == "pricing.html"] == ["free", "monthly"]


def test_company_account_gets_plan_numbers(app):
    client = company_client(app)
    new_course(client)
    with captured_templates(app) as rendered:
        client.get("/account")
        choose(client, "per_course")
        client.get("/account")
        choose(client, "monthly")
        client.get("/account")
    pages = [ctx for name, ctx in rendered if name == "account_company.html"]
    keys = ("plan_label", "course_limit", "courses_used", "can_create_course")
    assert [tuple(p[k] for k in keys) for p in pages] == [
        ("Free", 1, 1, False),
        ("Per course", 2, 1, True),
        ("Monthly", None, 1, True),
    ]


def test_builder_gets_video_numbers(app, fake_storage):
    client = company_client(app)
    new_course(client)
    course_id = last_course_id(app)
    add_video_lesson(client, course_id)
    with captured_templates(app) as rendered:
        client.get(f"/course/{course_id}/builder")
        choose(client, "monthly")
        client.get(f"/course/{course_id}/builder")
    pages = [ctx for name, ctx in rendered if name == "builder.html"]
    keys = ("video_limit", "videos_used", "can_add_video")
    assert [tuple(p[k] for k in keys) for p in pages] == [(3, 1, True), (None, 1, True)]


# ---------- plans.py ----------

def test_limits_by_plan(app):
    company_client(app)
    with app.app_context():
        user = User.query.filter_by(email="hr@acme.md").one()
        company = user.company

        company.plan, company.course_credits = "free", 5  # credits mean nothing on Free
        assert (plans.course_limit(user), plans.video_limit(user), company.is_pro) == (1, 3, False)

        company.plan, company.course_credits = "per_course", 2
        assert (plans.course_limit(user), plans.video_limit(user), company.is_pro) == (3, 10, True)

        company.plan = "monthly"
        assert (plans.course_limit(user), plans.video_limit(user), company.is_pro) == (None, None, True)
        assert user.is_pro is True

        company.plan = "something-old"  # an unknown value is treated as Free
        assert plans.plan_of(user) == "free" and plans.course_limit(user) == 1


# ---------- demo data and the database migration ----------

def test_demo_companies_are_on_the_top_plan(app):
    from database.models import CompanyProfile
    from database.seed import ensure_demo_data

    with app.app_context():
        ensure_demo_data()
        demo = CompanyProfile.query.join(User).filter(User.email.like("%@bitwise.demo")).all()
        assert demo and all(c.plan == "monthly" for c in demo)


def test_migration_0005_moves_is_pro_to_plan():
    pytest.importorskip("alembic")
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = os.path.join(os.path.dirname(__file__), "..", "migrations", "versions", "0005_company_plans.py")
    spec = importlib.util.spec_from_file_location("migration_0005", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE company_profile (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
            "name VARCHAR(120) NOT NULL, description VARCHAR(500), is_pro BOOLEAN NOT NULL)"))
        conn.execute(sa.text(
            "INSERT INTO company_profile (user_id, name, is_pro) VALUES (1, 'Free Co', 0), (2, 'Pro Co', 1)"))

        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()  # running it twice changes nothing

        columns = {c["name"] for c in sa.inspect(conn).get_columns("company_profile")}
        assert {"plan", "course_credits"} <= columns and "is_pro" not in columns
        rows = conn.execute(sa.text("SELECT name, plan, course_credits FROM company_profile ORDER BY id")).fetchall()
        assert [tuple(r) for r in rows] == [("Free Co", "free", 0), ("Pro Co", "monthly", 0)]