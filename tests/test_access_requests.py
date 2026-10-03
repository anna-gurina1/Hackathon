from database import db
from database.models import AccessRequest, Course, Enrollment, Lesson, User
from tests.conftest import signup_confirmed


def setup(app):
    company = app.test_client()
    signup_confirmed(company, {"type": "company", "company_name": "Bank", "email": "hr@bank.md"})
    person = app.test_client()
    signup_confirmed(person, {"type": "person", "first_name": "Ion", "last_name": "P", "email": "ion@x.md"})
    with app.app_context():
        bank = User.query.filter_by(email="hr@bank.md").one()
        course = Course(company_id=bank.id, title="Security", level="beginner",
                        status="published", is_private=True)
        db.session.add(course)
        db.session.flush()
        db.session.add(Lesson(course_id=course.id, order=1, title="L1", text="t"))
        db.session.commit()
        return company, person, course.id, course.invite_token


def test_private_course_page_shows_send_request(app):
    _, person, course_id, _ = setup(app)
    page = person.get(f"/course/{course_id}").get_data(as_text=True)
    assert "Send request" in page and "Start course" not in page


def test_cannot_start_or_open_lessons_without_acceptance(app):
    _, person, course_id, _ = setup(app)
    person.post(f"/course/{course_id}/start")
    with app.app_context():
        assert Enrollment.query.count() == 0
    assert person.get(f"/course/{course_id}/lesson/1").status_code == 403


def test_request_then_accept_lets_the_person_learn(app, capsys):
    company, person, course_id, _ = setup(app)
    response = person.post(f"/course/{course_id}/request", follow_redirects=True)
    assert b"Waiting for approval" in response.data
    assert "EMAIL to: hr@bank.md" in capsys.readouterr().out  # the company is told

    account = company.get("/account").get_data(as_text=True)
    assert "Requests to join" in account and "ion@x.md" in account
    with app.app_context():
        request_id = AccessRequest.query.one().id

    company.post(f"/course/{course_id}/requests/{request_id}/accept")
    assert "EMAIL to: ion@x.md" in capsys.readouterr().out  # the person is told
    with app.app_context():
        assert AccessRequest.query.one().status == "accepted"
        assert Enrollment.query.filter_by(course_id=course_id).count() == 1
    assert person.get(f"/course/{course_id}/lesson/1").status_code == 200
    assert "Requests to join" not in company.get("/account").get_data(as_text=True)


def test_decline(app):
    company, person, course_id, _ = setup(app)
    person.post(f"/course/{course_id}/request")
    with app.app_context():
        request_id = AccessRequest.query.one().id
    company.post(f"/course/{course_id}/requests/{request_id}/decline")
    with app.app_context():
        assert AccessRequest.query.one().status == "declined"
        assert Enrollment.query.count() == 0
    assert "Declined" in person.get("/account").get_data(as_text=True)
    assert "declined your request" in person.get(f"/course/{course_id}").get_data(as_text=True)


def test_only_the_owner_can_accept(app):
    company, person, course_id, _ = setup(app)
    person.post(f"/course/{course_id}/request")
    with app.app_context():
        request_id = AccessRequest.query.one().id
    other = app.test_client()
    signup_confirmed(other, {"type": "company", "company_name": "Other", "email": "o@o.md"})
    assert other.post(f"/course/{course_id}/requests/{request_id}/accept").status_code == 403
    assert person.post(f"/course/{course_id}/requests/{request_id}/accept").status_code == 403


def test_invite_link_still_lets_start_directly(app):
    _, person, course_id, token = setup(app)
    page = person.get(f"/course/private/{token}").get_data(as_text=True)
    assert "Start course" in page
    person.post(f"/course/{course_id}/start", data={"invite": token})
    assert person.get(f"/course/{course_id}/lesson/1").status_code == 200


def test_request_is_not_duplicated(app):
    _, person, course_id, _ = setup(app)
    person.post(f"/course/{course_id}/request")
    person.post(f"/course/{course_id}/request")
    with app.app_context():
        assert AccessRequest.query.count() == 1


def test_public_course_cannot_be_requested(app):
    company, person, _, _ = setup(app)
    with app.app_context():
        bank = User.query.filter_by(email="hr@bank.md").one()
        course = Course(company_id=bank.id, title="Open", level="beginner", status="published")
        db.session.add(course)
        db.session.commit()
        public_id = course.id
    assert person.post(f"/course/{public_id}/request").status_code == 404
