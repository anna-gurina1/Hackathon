from flask_login import AnonymousUserMixin

from database import db
from database.models import (
    CompanyProfile,
    Course,
    Enrollment,
    Lesson,
    Offer,
    PersonProfile,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    User,
)
from database.queries import (
    best_score,
    company_dashboard,
    course_visible_to,
    person_dashboard,
    search_companies,
)


# --- helpers --------------------------------------------------------------

def _make_company(email, name="Acme Construction", description=None):
    user = User(type="company", email=email)
    user.company = CompanyProfile(name=name, description=description)
    db.session.add(user)
    db.session.flush()
    return user


def _make_person(email, first="Demo", last="Person"):
    user = User(type="person", email=email)
    user.person = PersonProfile(first_name=first, last_name=last)
    db.session.add(user)
    db.session.flush()
    return user


def _make_course(company, **overrides):
    defaults = dict(
        company_id=company.id,
        title="Test course",
        topic="Concrete",
        profession="Builder",
        outcome="Learn to pour concrete",
        level="beginner",
        knowledge_type="procedure",
        duration=5,
        is_private=False,
        status="published",
    )
    defaults.update(overrides)
    course = Course(**defaults)
    db.session.add(course)
    db.session.flush()
    return course


def _make_lesson_with_quiz(course, order=1, pass_score=70, correct_text="Right"):
    lesson = Lesson(course_id=course.id, order=order, title=f"Lesson {order}", text="...")
    db.session.add(lesson)
    db.session.flush()

    quiz = Quiz(lesson_id=lesson.id, pass_score=pass_score)
    db.session.add(quiz)
    db.session.flush()

    question = QuizQuestion(quiz_id=quiz.id, text="Question?", category="goal")
    db.session.add(question)
    db.session.flush()

    db.session.add(QuizAnswer(question_id=question.id, text=correct_text, is_correct=True))
    db.session.add(QuizAnswer(question_id=question.id, text="Wrong", is_correct=False))
    db.session.flush()

    return lesson, quiz


def _enroll(user, course, status="in_progress", current_lesson=1, completed_at=None):
    enrollment = Enrollment(
        user_id=user.id,
        course_id=course.id,
        status=status,
        current_lesson=current_lesson,
        completed_at=completed_at,
    )
    db.session.add(enrollment)
    db.session.flush()
    return enrollment


# --- course_visible_to ------------------------------------------------------

def test_public_published_course_visible_to_anyone(app):
    with app.app_context():
        company = _make_company("owner1@test.md")
        stranger = _make_person("stranger1@test.md")
        course = _make_course(company, is_private=False, status="published")

        assert course_visible_to(course, stranger) is True
        assert course_visible_to(course, AnonymousUserMixin()) is True


def test_private_course_hidden_from_stranger(app):
    with app.app_context():
        company = _make_company("owner2@test.md")
        stranger = _make_person("stranger2@test.md")
        course = _make_course(company, is_private=True, status="published")

        assert course_visible_to(course, stranger) is False
        assert course_visible_to(course, AnonymousUserMixin()) is False


def test_private_course_visible_to_owner(app):
    with app.app_context():
        company = _make_company("owner3@test.md")
        course = _make_course(company, is_private=True, status="published")

        assert course_visible_to(course, company) is True


def test_private_course_visible_to_enrolled_user(app):
    with app.app_context():
        company = _make_company("owner4@test.md")
        person = _make_person("person4@test.md")
        course = _make_course(company, is_private=True, status="published")
        _enroll(person, course)

        assert course_visible_to(course, person) is True


def test_draft_course_hidden_from_non_owner(app):
    with app.app_context():
        company = _make_company("owner5@test.md")
        stranger = _make_person("stranger5@test.md")
        course = _make_course(company, is_private=False, status="draft")

        assert course_visible_to(course, stranger) is False
        assert course_visible_to(course, company) is True


# --- search_companies --------------------------------------------------------

def test_search_by_topic_matches_public_course(app):
    with app.app_context():
        company = _make_company("search1@test.md", name="Rebar Pros")
        _make_course(company, topic="Rebar inspection", is_private=False, status="published")

        results = search_companies("rebar", "topic")

        assert len(results) == 1
        assert results[0]["name"] == "Rebar Pros"
        assert results[0]["course_count"] == 1
        assert results[0]["url"] == f"/company/{company.id}"


def test_search_finds_companies_with_private_courses(app):
    with app.app_context():
        company = _make_company("search2@test.md", name="Private Co")
        _make_course(company, topic="Rebar inspection", is_private=True, status="published")

        results = search_companies("rebar", "topic")

        assert [r["name"] for r in results] == ["Private Co"]


def test_search_excludes_draft_courses(app):
    with app.app_context():
        company = _make_company("search3@test.md", name="Draft Co")
        _make_course(company, topic="Rebar inspection", is_private=False, status="draft")

        results = search_companies("rebar", "topic")

        assert results == []


def test_search_empty_query_returns_all_public_companies(app):
    with app.app_context():
        company = _make_company("search4@test.md", name="Any Co")
        _make_course(company, is_private=False, status="published")

        results = search_companies("", "topic")

        assert len(results) == 1
        assert results[0]["name"] == "Any Co"


def test_search_unknown_by_returns_empty_list(app):
    with app.app_context():
        company = _make_company("search5@test.md")
        _make_course(company, is_private=False, status="published")

        assert search_companies("anything", "nonsense") == []


# --- person_dashboard ---------------------------------------------------------

def test_person_dashboard_counts_started_and_completed(app):
    with app.app_context():
        company = _make_company("pd_owner@test.md")
        person = _make_person("pd_person@test.md")

        course_a = _make_course(company, title="Course A")
        course_b = _make_course(company, title="Course B")

        _enroll(person, course_a, status="in_progress")
        _enroll(person, course_b, status="completed")

        db.session.add(Offer(company_id=company.id, user_id=person.id, course_id=course_b.id, text="Join us!"))
        db.session.flush()

        result = person_dashboard(person)

        assert result["stats"] == {"started": 2, "completed": 1}
        assert len(result["enrollments"]) == 2
        assert len(result["offers"]) == 1
        assert result["offers"][0].text == "Join us!"


def test_person_dashboard_empty_for_new_user(app):
    with app.app_context():
        person = _make_person("pd_new@test.md")

        result = person_dashboard(person)

        assert result == {
            "enrollments": [],
            "stats": {"started": 0, "completed": 0},
            "offers": [],
            "requests": [],
        }


# --- company_dashboard ---------------------------------------------------------

def test_company_dashboard_courses_and_counts(app):
    with app.app_context():
        company = _make_company("cd_owner@test.md")
        person1 = _make_person("cd_person1@test.md")
        person2 = _make_person("cd_person2@test.md")

        course = _make_course(company, is_private=True)
        _enroll(person1, course, status="in_progress")
        _enroll(person2, course, status="completed")

        result = company_dashboard(company)

        assert len(result["courses"]) == 1
        row = result["courses"][0]
        assert row["course"].id == course.id
        assert row["enrolled"] == 2
        assert row["completed"] == 1
        assert row["invite_url"] == f"/course/private/{course.invite_token}"


def test_company_dashboard_public_course_has_no_invite_url(app):
    with app.app_context():
        company = _make_company("cd_owner2@test.md")
        course = _make_course(company, is_private=False)

        result = company_dashboard(company)

        assert result["courses"][0]["invite_url"] is None


def test_company_dashboard_candidates_only_from_own_courses(app):
    with app.app_context():
        company_a = _make_company("cd_companyA@test.md")
        company_b = _make_company("cd_companyB@test.md")
        person = _make_person("cd_candidate@test.md")

        course_a = _make_course(company_a, title="A course")
        course_b = _make_course(company_b, title="B course")

        _enroll(person, course_a, status="completed")
        _enroll(person, course_b, status="completed")

        result = company_dashboard(company_a)

        candidate_course_ids = {c["course"].id for c in result["candidates"]}
        assert candidate_course_ids == {course_a.id}


def test_company_dashboard_candidate_fields_and_offer_sent_flag(app):
    with app.app_context():
        company = _make_company("cd_owner3@test.md")
        person = _make_person("cd_candidate2@test.md")
        course = _make_course(company)

        _, quiz = _make_lesson_with_quiz(course)
        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz.id, score=90, passed=True))
        db.session.flush()

        _enroll(person, course, status="completed")

        result = company_dashboard(company)
        candidate = result["candidates"][0]

        assert candidate["user"].id == person.id
        assert candidate["score"] == 90
        assert candidate["offer_sent"] is False

        db.session.add(Offer(company_id=company.id, user_id=person.id, course_id=course.id, text="Hi"))
        db.session.flush()

        result_after_offer = company_dashboard(company)
        assert result_after_offer["candidates"][0]["offer_sent"] is True


# --- best_score ----------------------------------------------------------------

def test_best_score_returns_highest_of_several_attempts(app):
    with app.app_context():
        company = _make_company("bs_owner@test.md")
        person = _make_person("bs_person@test.md")
        course = _make_course(company)
        _, quiz = _make_lesson_with_quiz(course)

        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz.id, score=40, passed=False))
        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz.id, score=85, passed=True))
        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz.id, score=60, passed=False))
        db.session.flush()

        assert best_score(person.id, course.id) == 85


def test_best_score_none_when_no_attempts(app):
    with app.app_context():
        company = _make_company("bs_owner2@test.md")
        person = _make_person("bs_person2@test.md")
        course = _make_course(company)
        _make_lesson_with_quiz(course)

        assert best_score(person.id, course.id) is None


def test_best_score_ignores_other_courses(app):
    with app.app_context():
        company = _make_company("bs_owner3@test.md")
        person = _make_person("bs_person3@test.md")
        course_a = _make_course(company, title="Course A")
        course_b = _make_course(company, title="Course B")
        _, quiz_a = _make_lesson_with_quiz(course_a)
        _, quiz_b = _make_lesson_with_quiz(course_b)

        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz_a.id, score=50, passed=True))
        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz_b.id, score=95, passed=True))
        db.session.flush()

        assert best_score(person.id, course_a.id) == 50
        assert best_score(person.id, course_b.id) == 95


# --- cascade delete (the bug you found) -----------------------------------

def test_deleting_course_removes_quiz_attempts(app):
    with app.app_context():
        company = _make_company("cascade_owner@test.md")
        person = _make_person("cascade_person@test.md")
        course = _make_course(company)
        _, quiz = _make_lesson_with_quiz(course)

        db.session.add(QuizAttempt(user_id=person.id, quiz_id=quiz.id, score=70, passed=True))
        db.session.commit()

        quiz_id = quiz.id
        assert QuizAttempt.query.filter_by(quiz_id=quiz_id).count() == 1

        db.session.delete(course)
        db.session.commit()

        assert QuizAttempt.query.filter_by(quiz_id=quiz_id).count() == 0