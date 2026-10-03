from database import db
from database.models import Course, User
from tests.conftest import signup_confirmed


def setup_courses(app):
    signup_confirmed(app.test_client(), {"type": "company", "company_name": "BuildRight", "email": "hr@b.md"})
    with app.app_context():
        company = User.query.filter_by(email="hr@b.md").one()
        db.session.add_all([
            Course(company_id=company.id, title="Rebar check", topic="Concrete", profession="Builder",
                   outcome="Check rebar", level="beginner", status="published"),
            Course(company_id=company.id, title="Secret", topic="Concrete", level="beginner",
                   status="published", is_private=True),
            Course(company_id=company.id, title="Draft", topic="Concrete", level="beginner", status="draft"),
        ])
        db.session.commit()
        return company.id, Course.query.filter_by(title="Rebar check").one().id


def test_search_by_topic_returns_courses(app):
    company_id, course_id = setup_courses(app)
    results = app.test_client().get("/api/search?q=concrete&by=topic").get_json()
    assert sorted(r["title"] for r in results) == ["Rebar check", "Secret"]  # drafts are never found
    results = [r for r in results if r["title"] == "Rebar check"]
    assert results[0]["type"] == "course"
    assert results[0]["url"] == f"/course/{course_id}"
    assert results[0]["company_url"] == f"/company/{company_id}"


def test_search_by_title_profession_and_result(app):
    setup_courses(app)
    client = app.test_client()
    assert [r["title"] for r in client.get("/api/search?q=rebar&by=topic").get_json()] == ["Rebar check"]
    assert [r["title"] for r in client.get("/api/search?q=build&by=profession").get_json()] == ["Rebar check"]
    assert [r["title"] for r in client.get("/api/search?q=check&by=result").get_json()] == ["Rebar check"]


def test_search_by_company_returns_companies(app):
    company_id, _ = setup_courses(app)
    results = app.test_client().get("/api/search?q=build&by=company").get_json()
    assert results[0]["type"] == "company"
    assert results[0]["url"] == f"/company/{company_id}"
