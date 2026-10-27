"""Boundary failures must not turn saved work into an apparent server failure.

External services are mocked. These tests never send email or touch Cloudinary.
"""

import pytest

from backend import email, uploads
from core.questions import QUESTIONS
from database import db
from database.models import Enrollment, Offer


@pytest.mark.parametrize("payload", [["not-an-object"], "text", 123, True])
def test_translation_rejects_non_object_json(app, payload):
    response = app.test_client().post("/api/translate", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"error": "bad_source"}


@pytest.mark.parametrize(
    "sources", [None, [], [None], [12], [{"token": "not-a-string"}], [""]]
)
def test_translation_rejects_invalid_sources_before_service_call(
    app, monkeypatch, sources
):
    def unexpected_call(*args, **kwargs):
        pytest.fail("Malformed sources must not reach the translation service")

    monkeypatch.setattr("backend.routes.main.translate_sources", unexpected_call)
    assert (
        app.test_client().post("/api/translate", json={"sources": sources}).status_code
        == 400
    )


@pytest.mark.parametrize("helper", ["delete_image", "delete_video", "delete_document"])
def test_cleanup_without_storage_configuration_returns_false(app, monkeypatch, helper):
    def missing_configuration():
        raise RuntimeError("Storage is not configured")

    monkeypatch.setattr(uploads, "_configure", missing_configuration)
    assert getattr(uploads, helper)("synthetic-asset") is False


@pytest.mark.parametrize("helper", ["delete_image", "delete_video", "delete_document"])
def test_cleanup_network_failure_returns_false(app, monkeypatch, helper):
    monkeypatch.setattr(uploads, "_configure", lambda: None)

    def unavailable(*args, **kwargs):
        raise OSError("Synthetic storage failure")

    monkeypatch.setattr(uploads.cloudinary.uploader, "destroy", unavailable)
    assert getattr(uploads, helper)("synthetic-asset") is False


@pytest.mark.parametrize("helper", ["delete_image", "delete_video", "delete_document"])
def test_cleanup_success_still_returns_true(app, monkeypatch, helper):
    monkeypatch.setattr(uploads, "_configure", lambda: None)
    monkeypatch.setattr(
        uploads.cloudinary.uploader, "destroy", lambda *args, **kwargs: {"result": "ok"}
    )
    assert getattr(uploads, helper)("synthetic-asset") is True


def test_production_without_mail_transport_does_not_print_login_body(app, capsys):
    app.config.update(APP_ENV="production", MAIL_SERVER="", BREVO_API_KEY="")
    assert (
        email.send_email("person@example.invalid", "Login", "sensitive-test-link")
        is False
    )
    assert "sensitive-test-link" not in capsys.readouterr().out


def test_production_demo_recipient_does_not_print_login_body(app, capsys):
    app.config.update(
        APP_ENV="production", MAIL_SERVER="smtp.example.invalid", BREVO_API_KEY=""
    )
    assert (
        email.send_email("person@bitwise.demo", "Login", "sensitive-test-link") is False
    )
    assert "sensitive-test-link" not in capsys.readouterr().out


def test_development_console_mail_remains_available(app, capsys):
    app.config.update(APP_ENV="development", MAIL_SERVER="", BREVO_API_KEY="")
    assert (
        email.send_email("person@example.invalid", "Login", "local-test-link") is True
    )
    assert "local-test-link" in capsys.readouterr().out


def test_multiline_course_title_does_not_break_email_headers(app, monkeypatch):
    app.config.update(
        APP_ENV="development",
        MAIL_SERVER="smtp.example.invalid",
        MAIL_BACKGROUND=False,
        MAIL_FROM="Bitwise <sender@example.invalid>",
        BREVO_API_KEY="",
    )
    delivered = []
    monkeypatch.setattr(
        email,
        "_deliver",
        lambda settings, message, logger: delivered.append(message) or True,
    )
    assert (
        email.send_email(
            "person@example.invalid", "Course title\r\nsecond line", "Body"
        )
        is True
    )
    assert str(delivered[0]["Subject"]) == "Course title second line"


@pytest.mark.parametrize("failure", ["return_false", "raise"])
def test_saved_offer_survives_mail_failure(data, login, monkeypatch, failure):
    course, learner = data["published"], data["learner"]
    db.session.add(
        Enrollment(user_id=learner.id, course_id=course.id, status="completed")
    )
    db.session.commit()
    client = login(data["owner"], company_id=data["alpha"].id)

    def failed_mail(*args, **kwargs):
        if failure == "raise":
            raise RuntimeError("Synthetic mail failure")
        return False

    monkeypatch.setattr("backend.routes.quiz.send_email", failed_mail)
    response = client.post(
        f"/offer/{learner.id}/{course.id}",
        data={"text": "An actual saved offer"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "email could not be sent" in response.get_data(as_text=True)
    assert Offer.query.filter_by(user_id=learner.id, course_id=course.id).count() == 1
    learner_client = login(learner)
    assert "An actual saved offer" in learner_client.get("/account").get_data(
        as_text=True
    )


def test_course_completion_survives_notification_exception(data, login, monkeypatch):
    course, learner = data["published"], data["learner"]
    client = login(learner)
    client.post(f"/course/{course.id}/start")

    def failed_mail(*args, **kwargs):
        raise RuntimeError("Synthetic mail failure")

    monkeypatch.setattr("backend.routes.quiz.send_email", failed_mail)
    quiz = course.lessons[0].quiz
    answers = {
        f"q_{question.id}": next(str(a.id) for a in question.answers if a.is_correct)
        for question in quiz.questions
    }
    response = client.post(f"/course/{course.id}/lesson/1/quiz", data=answers)
    assert response.status_code == 200
    enrollment = Enrollment.query.filter_by(
        user_id=learner.id, course_id=course.id
    ).one()
    assert enrollment.status == "completed"
    assert enrollment.completed_at is not None


def test_studio_checkbox_does_not_redirect_to_external_referrer(data, login):
    course = data["assigned"]
    client = login(data["owner"], company_id=data["alpha"].id)
    question_id = QUESTIONS[0]["id"]
    response = client.post(
        f"/course/{course.id}/questions/{question_id}/answered",
        headers={"Referer": "https://outside.example.invalid"},
    )
    assert response.status_code == 302
    assert response.location == f"/course/{course.id}/builder"


def test_test_uploads_are_isolated_and_portable(app, tmp_path):
    from pathlib import Path

    path = Path(app.config["UPLOAD_FOLDER"])
    assert path.is_relative_to(tmp_path)
