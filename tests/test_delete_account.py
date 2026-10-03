from datetime import datetime

from database import db
from database.models import (Course, Enrollment, Lesson, Offer, Quiz, QuizAttempt, User)
from tests.conftest import signup_confirmed


def make_people(app):
    company = app.test_client()
    signup_confirmed(company, {"type": "company", "company_name": "Acme", "email": "hr@acme.md"})
    person = app.test_client()
    signup_confirmed(person, {"type": "person", "first_name": "Ion", "last_name": "P", "email": "ion@x.md"})

    with app.app_context():
        hr = User.query.filter_by(email="hr@acme.md").one()
        ion = User.query.filter_by(email="ion@x.md").one()
        course = Course(company_id=hr.id, title="T", level="beginner", status="published")
        db.session.add(course)
        db.session.flush()
        lesson = Lesson(course_id=course.id, order=1, title="L", text="t", video_filename="video-1")
        db.session.add(lesson)
        db.session.flush()
        quiz = Quiz(lesson_id=lesson.id)
        db.session.add(quiz)
        db.session.flush()
        db.session.add(QuizAttempt(user_id=ion.id, quiz_id=quiz.id, score=100, passed=True))
        db.session.add(Enrollment(user_id=ion.id, course_id=course.id, status="completed",
                                  completed_at=datetime(2026, 10, 3)))
        db.session.add(Offer(company_id=hr.id, user_id=ion.id, course_id=course.id, text="Join us"))
        db.session.commit()
    return company, person


def test_account_page_shows_delete_block(app):
    company, person = make_people(app)
    assert "Delete my account" in person.get("/account").get_data(as_text=True)
    assert "all your courses" in company.get("/account").get_data(as_text=True)


def test_wrong_email_keeps_account(app):
    _, person = make_people(app)
    response = person.post("/account/delete", data={"confirm_email": "other@x.md"}, follow_redirects=True)
    assert b"does not match" in response.data
    with app.app_context():
        assert User.query.filter_by(email="ion@x.md").count() == 1


def test_person_deletes_account(app):
    _, person = make_people(app)
    response = person.post("/account/delete", data={"confirm_email": " ION@x.md "}, follow_redirects=True)
    assert b"has been deleted" in response.data
    with app.app_context():
        assert User.query.filter_by(email="ion@x.md").count() == 0
        assert Enrollment.query.count() == 0
        assert QuizAttempt.query.count() == 0
        assert Offer.query.count() == 0
        assert Course.query.count() == 1  # the company's course stays
    assert person.get("/account").status_code == 302  # logged out


def test_company_deletes_account_with_courses_and_videos(app, monkeypatch):
    deleted = []
    monkeypatch.setattr("backend.routes.main.delete_video", deleted.append)
    company, person = make_people(app)
    company.post("/account/delete", data={"confirm_email": "hr@acme.md"})
    with app.app_context():
        assert User.query.filter_by(email="hr@acme.md").count() == 0
        assert Course.query.count() == 0
        assert Lesson.query.count() == 0
        assert Enrollment.query.count() == 0
        assert Offer.query.count() == 0
        assert User.query.filter_by(email="ion@x.md").count() == 1  # learners stay
    assert deleted == ["video-1"]
    assert person.get("/account").status_code == 200


def test_guest_cannot_delete(client):
    assert client.post("/account/delete", data={"confirm_email": "x@x.md"}).status_code == 302
