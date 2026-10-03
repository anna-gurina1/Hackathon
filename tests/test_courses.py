from database import db
from database.models import Course, Enrollment, Lesson, Quiz, User


# ---------- helpers ----------

def _signup_company(app, name, email):
    client = app.test_client()
    client.post("/signup", data={"type": "company", "company_name": name, "email": email})
    return client


def _signup_person(app, email):
    # NOTE: person form field names (first_name / last_name) are assumed from PersonProfile
    client = app.test_client()
    client.post(
        "/signup",
        data={"type": "person", "first_name": "Ion", "last_name": "Popescu", "email": email},
    )
    return client


def _make_course(app, company_email, title="Welding basics", topic="Welding",
                 is_private=False, status="published", lessons=2):
    with app.app_context():
        company = User.query.filter_by(email=company_email).one()
        course = Course(
            company_id=company.id,
            title=title,
            description="d",
            topic=topic,
            profession="Welder",
            outcome="Weld a seam",
            level="beginner",
            knowledge_type="procedure",
            duration=5,
            is_private=is_private,
            status=status,
        )
        db.session.add(course)
        db.session.flush()
        for i in range(1, lessons + 1):
            lesson = Lesson(course_id=course.id, order=i, title=f"Lesson {i}")
            db.session.add(lesson)
            db.session.flush()
            db.session.add(Quiz(lesson_id=lesson.id, pass_score=70))
        db.session.commit()
        return course.id, course.invite_token


# ---------- tests ----------

def test_private_course_needs_token(app):
    _signup_company(app, "Acme", "a@acme.md")
    course_id, token = _make_course(app, "a@acme.md", is_private=True)
    guest = app.test_client()

    assert guest.get(f"/course/{course_id}").status_code == 404
    assert guest.get("/course/private/wrong-token").status_code == 404
    assert guest.get(f"/course/private/{token}").status_code == 200


def test_person_cannot_create_course(app):
    person = _signup_person(app, "ion@test.md")
    assert person.get("/course/new").status_code == 403
    resp = person.post("/course/new", data={"title": "Nope"})
    assert resp.status_code == 403


def test_company_creates_course_and_goes_to_builder(app):
    company = _signup_company(app, "Acme", "a@acme.md")
    resp = company.post(
        "/course/new",
        data={
            "title": "Welding basics",
            "description": "d",
            "topic": "Welding",
            "profession": "Welder",
            "outcome": "Weld a seam",
            "level": "beginner",
            "knowledge_type": "procedure",
            "duration": "5",
            "visibility": "public",
        },
    )
    assert resp.status_code == 302
    assert "/builder" in resp.headers["Location"]
    with app.app_context():
        assert Course.query.filter_by(title="Welding basics").count() == 1


def test_cannot_open_lesson_2_before_passing_quiz(app):
    _signup_company(app, "Acme", "a@acme.md")
    course_id, _ = _make_course(app, "a@acme.md")
    person = _signup_person(app, "ion@test.md")

    resp = person.post(f"/course/{course_id}/start")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/course/{course_id}/lesson/1")

    with app.app_context():
        assert Enrollment.query.filter_by(course_id=course_id).one().current_lesson == 1

    assert person.get(f"/course/{course_id}/lesson/1").status_code == 200
    assert person.get(f"/course/{course_id}/lesson/2").status_code == 403


def test_private_course_not_in_search(app):
    # Acme has only a private course; Beta has a public one (control: search itself works)
    _signup_company(app, "Acme", "a@acme.md")
    _signup_company(app, "Beta", "b@beta.md")
    _make_course(app, "a@acme.md", topic="Welding", is_private=True)
    _make_course(app, "b@beta.md", topic="Welding", is_private=False)

    resp = app.test_client().get("/api/search?q=Welding&by=topic")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()]
    assert "Beta" in names
    assert "Acme" not in names
