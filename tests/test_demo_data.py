from database import db
from database.models import Course, Enrollment, Lesson, User
from database.queries import company_dashboard, search_courses
from database.seed import DEMO_COMPANIES, DEMO_LEARNERS, add_demo_data, reset_to_demo


def test_demo_data_is_added_once(app):
    with app.app_context():
        add_demo_data()
        add_demo_data()  # second start of the server: nothing is duplicated
        assert User.query.filter_by(type="company").count() == len(DEMO_COMPANIES)
        assert Course.query.count() == len(DEMO_COMPANIES)
        assert User.query.filter_by(type="person").count() == len(DEMO_LEARNERS)
        for course in Course.query.all():
            assert course.status == "published"
            assert course.lesson_count >= 3
            assert all(lesson.quiz and len(lesson.quiz.questions) == 2 for lesson in course.lessons)


def test_private_bank_course_is_found_and_has_requests(app):
    with app.app_context():
        add_demo_data()
        results = {c["title"]: c["is_private"] for c in search_courses("", "topic")}
        assert len(results) == 4
        bank_title = next(t for t in results if "Cyber hygiene" in t)
        assert results[bank_title] is True
        bank = User.query.filter_by(email="victoriabank@bitwise.demo").one()
        assert len(company_dashboard(bank)["requests"]) == 2


def test_companies_see_demo_candidates(app):
    with app.app_context():
        add_demo_data()
        allied = User.query.filter_by(email="alliedtesting@bitwise.demo").one()
        candidates = company_dashboard(allied)["candidates"]
        assert {c["user"].email for c in candidates} == {"ana.popescu@bitwise.demo", "maria.ceban@bitwise.demo"}
        assert all(c["score"] for c in candidates)


def test_reset_removes_everything_else(app, client):
    from tests.conftest import signup_confirmed
    signup_confirmed(client, {"type": "company", "company_name": "Junk", "email": "junk@x.md"})
    with app.app_context():
        junk = User.query.filter_by(email="junk@x.md").one()
        db.session.add(Course(company_id=junk.id, title="ИП", level="beginner", status="published"))
        db.session.commit()
        reset_to_demo()
        assert User.query.filter_by(email="junk@x.md").count() == 0
        assert Course.query.filter_by(title="ИП").count() == 0
        assert Course.query.count() == len(DEMO_COMPANIES)


def test_old_buildright_demo_is_removed(app):
    with app.app_context():
        old = User(type="company", email="demo-company@test.md")
        db.session.add(old)
        db.session.flush()
        course = Course(company_id=old.id, title="How to check rebar before concreting", level="beginner")
        db.session.add(course)
        db.session.flush()
        db.session.add(Lesson(course_id=course.id, order=1, title="L"))
        db.session.commit()
        add_demo_data()
        assert User.query.filter_by(email="demo-company@test.md").count() == 0
        assert Course.query.filter_by(title="How to check rebar before concreting").count() == 0


def test_demo_emails_are_printed_even_with_real_smtp(app, capsys):
    from backend.email import send_email
    app.config["MAIL_SERVER"] = "smtp.example.com"
    with app.test_request_context():
        assert send_email("diez@bitwise.demo", "Hi", "link")
    assert "EMAIL to: diez@bitwise.demo" in capsys.readouterr().out


def test_demo_companies_have_logos(app):
    with app.app_context():
        add_demo_data()
        with app.test_request_context():
            for company in User.query.filter_by(type="company").all():
                assert company.avatar.startswith("static:img/demo/")
                assert company.avatar_url.startswith("/static/img/demo/")
    client = app.test_client()
    assert client.get("/static/img/demo/diez.png").status_code == 200
    results = client.get("/api/search?q=&by=company").get_json()
    assert all(r["avatar_url"].startswith("/static/img/demo/") for r in results)
