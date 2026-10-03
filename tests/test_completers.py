from datetime import datetime

from database import db
from database.models import Course, Enrollment, User
from database.queries import company_dashboard


def test_course_card_lists_completers(app):
    client = app.test_client()
    client.post("/signup", data={"type": "company", "company_name": "Acme", "email": "hr@acme.md"})
    other = app.test_client()
    other.post("/signup", data={"type": "person", "first_name": "Ion", "last_name": "P", "email": "ion@x.md"})
    third = app.test_client()
    third.post("/signup", data={"type": "person", "first_name": "Ana", "last_name": "G", "email": "ana@x.md"})

    with app.app_context():
        company = User.query.filter_by(email="hr@acme.md").one()
        course = Course(company_id=company.id, title="T", level="beginner", knowledge_type="procedure",
                        duration=3, status="published")
        db.session.add(course)
        db.session.flush()
        ion = User.query.filter_by(email="ion@x.md").one()
        ana = User.query.filter_by(email="ana@x.md").one()
        db.session.add(Enrollment(user_id=ion.id, course_id=course.id, status="completed",
                                  completed_at=datetime(2026, 10, 3, 20, 0)))
        db.session.add(Enrollment(user_id=ana.id, course_id=course.id, status="in_progress"))
        db.session.commit()

        row = company_dashboard(company)["courses"][0]
        assert [p["email"] for p in row["completers"]] == ["ion@x.md"]

    page = client.get("/account").get_data(as_text=True)
    assert "Completed by" in page
    assert "mailto:ion@x.md" in page
    assert "ana@x.md" not in page
