import io
from datetime import datetime

from database import db
from database.models import Course, Enrollment, Offer, User
from tests.conftest import signup_confirmed


def person_client(app, email="ion@x.md"):
    client = app.test_client()
    signup_confirmed(client, {"type": "person", "first_name": "Ion", "last_name": "P", "email": email})
    return client


def company_client(app, email="hr@acme.md"):
    client = app.test_client()
    signup_confirmed(client, {"type": "company", "company_name": "Acme", "email": email})
    return client


def fake_storage(monkeypatch):
    stored = {}

    def save(file_storage):
        name = f"img-{len(stored) + 1}"
        stored[name] = file_storage.read()
        return name

    monkeypatch.setattr("backend.routes.main.save_image", save)
    monkeypatch.setattr("backend.routes.main.delete_image", lambda name: stored.pop(name, None) is not None)
    monkeypatch.setattr("backend.uploads.image_url", lambda name, size=200: f"https://img.test/{name}.jpg")
    return stored


# ---------- sign-up: optional company description ----------

def test_signup_form_has_optional_company_description(client):
    page = client.get("/").get_data(as_text=True)
    assert 'name="description"' in page and "(optional)" in page


def test_company_signup_saves_description(app):
    client = app.test_client()
    signup_confirmed(client, {"type": "company", "company_name": "Acme", "description": "We build", "email": "a@a.md"})
    with app.app_context():
        assert User.query.filter_by(email="a@a.md").one().company.description == "We build"


# ---------- avatar ----------

def test_upload_and_replace_avatar(app, monkeypatch):
    stored = fake_storage(monkeypatch)
    client = person_client(app)

    client.post("/account/avatar", data={"avatar": (io.BytesIO(b"png1"), "me.png")},
                content_type="multipart/form-data")
    with app.app_context():
        assert User.query.filter_by(email="ion@x.md").one().avatar == "img-1"
    assert "https://img.test/img-1.jpg" in client.get("/account").get_data(as_text=True)

    client.post("/account/avatar", data={"avatar": (io.BytesIO(b"png2"), "me2.png")},
                content_type="multipart/form-data")
    with app.app_context():
        assert User.query.filter_by(email="ion@x.md").one().avatar == "img-2"
    assert "img-1" not in stored  # the old photo is deleted


def test_remove_avatar(app, monkeypatch):
    fake_storage(monkeypatch)
    client = company_client(app)
    client.post("/account/avatar", data={"avatar": (io.BytesIO(b"logo"), "logo.png")},
                content_type="multipart/form-data")
    client.post("/account/avatar/delete")
    with app.app_context():
        assert User.query.filter_by(email="hr@acme.md").one().avatar is None
    page = client.get("/account").get_data(as_text=True)
    assert "img.test" not in page


def test_bad_image_shows_error(app, monkeypatch):
    def broken(file_storage):
        raise ValueError("Unsupported image format.")
    monkeypatch.setattr("backend.routes.main.save_image", broken)
    response = person_client(app).post(
        "/account/avatar", data={"avatar": (io.BytesIO(b"x"), "x.exe")},
        content_type="multipart/form-data", follow_redirects=True)
    assert b"Unsupported image format" in response.data


def test_guest_cannot_upload_avatar(client):
    assert client.post("/account/avatar").status_code == 302


# ---------- company name opens the company page ----------

def test_company_name_links_to_company_page(app):
    company_client(app)
    person = person_client(app)
    with app.app_context():
        hr = User.query.filter_by(email="hr@acme.md").one()
        ion = User.query.filter_by(email="ion@x.md").one()
        course = Course(company_id=hr.id, title="Rebar", level="beginner", status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=ion.id, course_id=course.id))
        db.session.add(Offer(company_id=hr.id, user_id=ion.id, course_id=course.id, text="Join"))
        db.session.commit()
        company_url, course_id = f"/company/{hr.id}", course.id

    account = person.get("/account").get_data(as_text=True)
    assert account.count(f'href="{company_url}"') >= 2  # offer + course card
    assert f'href="{company_url}"' in person.get(f"/course/{course_id}").get_data(as_text=True)
    company_page = person.get(company_url).get_data(as_text=True)
    assert f'href="/course/{course_id}"' in company_page


def test_course_form_has_public_and_private(app):
    page = company_client(app).get("/course/new").get_data(as_text=True)
    assert 'value="public"' in page and 'value="private"' in page
    assert "PRO" not in page
