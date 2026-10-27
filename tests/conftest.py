import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from core import create_app
from database import db
from database.models import (
    User,
    PersonProfile,
    Company,
    Membership,
    Course,
    Lesson,
    Quiz,
    QuizQuestion,
    QuizAnswer,
    CourseEditor,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    MAIL_SERVER = ""
    MAIL_BACKGROUND = False
    PUBLIC_URL = "https://example.invalid"


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.routes.workspaces.send_email", lambda *a, **k: True)
    monkeypatch.setattr("backend.routes.site_auth.send_email", lambda *a, **k: True)
    monkeypatch.setattr("backend.routes.courses.send_email", lambda *a, **k: True)
    monkeypatch.setattr("backend.routes.quiz.send_email", lambda *a, **k: True)

    class IsolatedTestConfig(TestConfig):
        # pytest owns this directory, including on Windows. Never share user uploads.
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = create_app(IsolatedTestConfig)

    @application.before_request
    def fresh_login_state():
        # Tests keep an outer app context for DB assertions. Real requests do not
        # share its g, so clear Flask-Login's per-request cache between clients.
        from flask import g

        g.pop("_login_user", None)

    with application.app_context():
        # Foreign keys enabled in behavioral tests, not just the default SQLite mode.
        db.session.execute(db.text("PRAGMA foreign_keys=ON"))
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def data(app):
    users = []
    for name in ("owner", "other", "editor", "learner"):
        user = User(
            type="person",
            email=name + "@example.invalid",
            person=PersonProfile(first_name=name, last_name="Test"),
        )
        db.session.add(user)
        users.append(user)
    db.session.flush()
    owner, other, editor, learner = users
    alpha = Company(id=10, owner_id=owner.id, name="Alpha", plan="monthly")
    beta = Company(id=20, owner_id=other.id, name="Beta", plan="monthly")
    db.session.add_all([alpha, beta])
    db.session.flush()
    memberships = [
        Membership(company_id=alpha.id, user_id=owner.id, role="owner"),
        Membership(company_id=beta.id, user_id=other.id, role="owner"),
        Membership(company_id=alpha.id, user_id=editor.id, role="editor"),
        Membership(company_id=beta.id, user_id=editor.id, role="editor"),
    ]
    db.session.add_all(memberships)
    db.session.flush()
    assigned = Course(company_id=alpha.id, title="Assigned draft", level="beginner")
    unassigned = Course(company_id=alpha.id, title="Unassigned draft", level="beginner")
    published = make_course(alpha.id, "Public course", status="published")
    private = make_course(
        alpha.id, "Private course", status="published", mode="request"
    )
    db.session.add_all([assigned, unassigned])
    db.session.flush()
    db.session.add(CourseEditor(course_id=assigned.id, membership_id=memberships[2].id))
    db.session.commit()
    return dict(
        owner=owner,
        other=other,
        editor=editor,
        learner=learner,
        alpha=alpha,
        beta=beta,
        assigned=assigned,
        unassigned=unassigned,
        published=published,
        private=private,
        editor_membership=memberships[2],
    )


def make_course(company_id, title, status="draft", mode="public"):
    course = Course(
        company_id=company_id,
        title=title,
        level="beginner",
        status=status,
        access_mode=mode,
        is_private=mode != "public",
    )
    db.session.add(course)
    db.session.flush()
    lesson = Lesson(
        course_id=course.id, order=1, title="Lesson", text="Private learning content"
    )
    db.session.add(lesson)
    db.session.flush()
    quiz = Quiz(lesson=lesson, pass_score=70)
    question = QuizQuestion(quiz=quiz, text="Question?")
    db.session.add_all([quiz, question])
    db.session.flush()
    db.session.add_all(
        [
            QuizAnswer(question=question, text="Yes", is_correct=True),
            QuizAnswer(question=question, text="No", is_correct=False),
        ]
    )
    db.session.flush()
    return course


@pytest.fixture
def login(app):
    def authenticate(user, company_id=None):
        from backend.routes.site_auth import _serializer

        with app.test_request_context():
            token = _serializer().dumps({"id": user.id, "n": user.login_nonce})
        client = app.test_client()
        assert client.get("/login/" + token).status_code == 302
        db.session.refresh(user)
        if company_id is not None:
            assert (
                client.post(
                    "/workspaces/select", data={"company_id": company_id}
                ).status_code
                == 302
            )
        return client

    return authenticate
