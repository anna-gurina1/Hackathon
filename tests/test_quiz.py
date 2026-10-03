from database import db
from database.models import (
    Course,
    Enrollment,
    Lesson,
    Offer,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    User,
)


# ---------- helpers ----------

def _signup_company(app, name, email):
    client = app.test_client()
    client.post("/signup", data={"type": "company", "company_name": name, "email": email})
    return client


def _signup_person(app, email):
    client = app.test_client()
    client.post(
        "/signup",
        data={"type": "person", "first_name": "Ion", "last_name": "Popescu", "email": email},
    )
    return client


def _user_id(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).one().id


def _make_course(app, company_email, lessons=2):
    """Published course, every lesson has a quiz: 2 questions, 2 answers each
    (first answer is the correct one), pass_score 70."""
    with app.app_context():
        company = User.query.filter_by(email=company_email).one()
        course = Course(
            company_id=company.id,
            title="Welding basics",
            description="d",
            topic="Welding",
            profession="Welder",
            outcome="Weld a seam",
            level="beginner",
            knowledge_type="procedure",
            duration=5,
            status="published",
        )
        db.session.add(course)
        db.session.flush()
        for i in range(1, lessons + 1):
            lesson = Lesson(course_id=course.id, order=i, title=f"Lesson {i}")
            db.session.add(lesson)
            db.session.flush()
            quiz = Quiz(lesson_id=lesson.id, pass_score=70)
            db.session.add(quiz)
            db.session.flush()
            for q in range(1, 3):
                question = QuizQuestion(quiz_id=quiz.id, text=f"L{i} question {q}")
                db.session.add(question)
                db.session.flush()
                db.session.add(QuizAnswer(question_id=question.id, text="right", is_correct=True))
                db.session.add(QuizAnswer(question_id=question.id, text="wrong", is_correct=False))
        db.session.commit()
        return course.id


def _enroll(app, person_email, course_id, current_lesson=1, status="in_progress"):
    with app.app_context():
        db.session.add(
            Enrollment(
                user_id=User.query.filter_by(email=person_email).one().id,
                course_id=course_id,
                current_lesson=current_lesson,
                status=status,
            )
        )
        db.session.commit()


def _answers(app, course_id, n, correct):
    """Form data for the quiz of lesson n: all correct or all wrong answers."""
    with app.app_context():
        lesson = Lesson.query.filter_by(course_id=course_id, order=n).one()
        data = {}
        for question in lesson.quiz.questions:
            answer = next(a for a in question.answers if a.is_correct == correct)
            data[f"q_{question.id}"] = answer.id
        return data


def _current_lesson(app, person_email, course_id):
    with app.app_context():
        return Enrollment.query.filter_by(
            user_id=User.query.filter_by(email=person_email).one().id, course_id=course_id
        ).one().current_lesson


def _quiz_url(course_id, n):
    return f"/course/{course_id}/lesson/{n}/quiz"


# ---------- tests ----------

def test_failed_quiz_does_not_unlock_next_lesson(app):
    _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")
    person = _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id)

    resp = person.post(_quiz_url(course_id, 1), data=_answers(app, course_id, 1, correct=False))
    assert resp.status_code == 200

    assert _current_lesson(app, "ion@test.md", course_id) == 1
    with app.app_context():
        attempt = QuizAttempt.query.one()
        assert attempt.score == 0 and attempt.passed is False
    assert person.get(f"/course/{course_id}/lesson/2").status_code == 403


def test_passed_quiz_unlocks_next_lesson(app):
    _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")
    person = _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id)

    resp = person.post(_quiz_url(course_id, 1), data=_answers(app, course_id, 1, correct=True))
    assert resp.status_code == 200

    assert _current_lesson(app, "ion@test.md", course_id) == 2
    with app.app_context():
        attempt = QuizAttempt.query.one()
        assert attempt.score == 100 and attempt.passed is True
    assert person.get(f"/course/{course_id}/lesson/2").status_code == 200


def test_last_quiz_completes_course_and_emails_company(app, capsys):
    _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")
    person = _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id, current_lesson=2)
    capsys.readouterr()  # drop the signup output

    resp = person.post(_quiz_url(course_id, 2), data=_answers(app, course_id, 2, correct=True))
    assert resp.status_code == 200

    with app.app_context():
        enrollment = Enrollment.query.one()
        assert enrollment.status == "completed"
        assert enrollment.completed_at is not None

    out = capsys.readouterr().out
    assert "a@acme.md" in out
    assert "New candidate" in out
    assert "ion@test.md" in out


def test_retake_is_unlimited(app):
    _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")
    person = _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id)

    wrong = _answers(app, course_id, 1, correct=False)
    right = _answers(app, course_id, 1, correct=True)

    assert person.post(_quiz_url(course_id, 1), data=wrong).status_code == 200
    assert person.post(_quiz_url(course_id, 1), data=wrong).status_code == 200
    assert _current_lesson(app, "ion@test.md", course_id) == 1

    assert person.post(_quiz_url(course_id, 1), data=right).status_code == 200
    assert _current_lesson(app, "ion@test.md", course_id) == 2

    # an already passed quiz can be taken again, progress does not move back or forward
    assert person.get(_quiz_url(course_id, 1)).status_code == 200
    assert person.post(_quiz_url(course_id, 1), data=wrong).status_code == 200
    assert _current_lesson(app, "ion@test.md", course_id) == 2

    with app.app_context():
        assert QuizAttempt.query.count() == 4


def test_other_company_cannot_send_offer(app):
    _signup_company(app, "Acme", "a@acme.md")
    other = _signup_company(app, "Beta", "b@beta.md")
    course_id = _make_course(app, "a@acme.md")
    _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id, current_lesson=3, status="completed")

    resp = other.post(
        f"/offer/{_user_id(app, 'ion@test.md')}/{course_id}", data={"text": "Join us"}
    )
    assert resp.status_code == 403
    with app.app_context():
        assert Offer.query.count() == 0


def test_offer_is_saved_and_emailed(app, capsys):
    company = _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")
    _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id, current_lesson=3, status="completed")
    capsys.readouterr()

    resp = company.post(
        f"/offer/{_user_id(app, 'ion@test.md')}/{course_id}", data={"text": "Join our team!"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account")

    with app.app_context():
        offer = Offer.query.one()
        assert offer.text == "Join our team!"
        assert offer.course_id == course_id
        assert offer.company_id == _user_id(app, "a@acme.md")
        assert offer.user_id == _user_id(app, "ion@test.md")

    out = capsys.readouterr().out
    assert "ion@test.md" in out
    assert "Job offer from Acme" in out


def test_offer_needs_completed_course(app):
    company = _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")
    _signup_person(app, "ion@test.md")
    _enroll(app, "ion@test.md", course_id)  # still in progress

    resp = company.post(
        f"/offer/{_user_id(app, 'ion@test.md')}/{course_id}", data={"text": "Join us"}
    )
    assert resp.status_code == 404
    with app.app_context():
        assert Offer.query.count() == 0
