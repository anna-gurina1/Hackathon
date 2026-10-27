"""Behavior and SQL-query budgets for the catalog/dashboard refactor.

Counters measure SELECT statements of query helpers, not page latency or a load test.
All data is artificial and stored in an isolated in-memory database.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from backend.catalog import CatalogFilters, catalog_results
from database import db
from database.catalog import published_topics, search_companies, search_courses
from database.models import (
    AccessRequest,
    Company,
    Course,
    Enrollment,
    Offer,
    QuizAttempt,
)
from database.queries import best_score, company_dashboard
from conftest import make_course


@contextmanager
def select_statements():
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(db.engine, "before_cursor_execute", record)


@pytest.mark.parametrize(
    "language, expected", [("en", "en"), ("ru", "ru"), ("de", None), ("", None)]
)
def test_catalog_language_normalization(language, expected):
    filters = CatalogFilters.from_args(
        {"lang": language, "q": " Python ", "topic": " Web "}
    )
    assert filters.language == expected
    assert filters.query == "Python"
    assert filters.topic == "Web"


def test_html_and_api_preserve_unknown_mode_contract(app, data):
    assert CatalogFilters.from_args({"by": "unknown"}).mode == "unknown"
    assert (
        CatalogFilters.from_args({"by": "unknown"}, fallback_to_topic=True).mode
        == "topic"
    )
    assert app.test_client().get("/api/search?by=unknown").get_json() == []
    assert data["published"].title in app.test_client().get(
        "/explore?by=unknown"
    ).get_data(as_text=True)


def test_company_mode_ignores_course_only_filters(app, data):
    filters = CatalogFilters(
        query="Alpha", mode="company", language="xx", topic="Missing"
    )
    rows = catalog_results(filters)
    assert len(rows) == 1
    assert rows[0]["type"] == "company"
    assert rows[0]["name"] == "Alpha"


def test_company_count_includes_private_but_excludes_drafts(app, data):
    rows = search_companies("Alpha", "company")
    assert rows[0]["course_count"] == 2
    assert rows[0]["url"] == f"/company/{data['alpha'].id}"
    assert search_companies("", "unknown") == []


def test_company_count_counts_matching_courses_only(app, data):
    data["published"].topic = "Python"
    data["private"].topic = "Design"
    db.session.commit()
    assert search_companies("Python", "topic")[0]["course_count"] == 1


def test_published_topics_are_unique_sorted_and_nonempty(app, data):
    data["published"].topic = "Web"
    data["private"].topic = "Web"
    data["assigned"].topic = "Draft only"
    empty = Course(
        company_id=data["alpha"].id,
        title="Empty",
        level="beginner",
        status="published",
        topic="",
    )
    db.session.add(empty)
    db.session.commit()
    assert published_topics() == ["Web"]


def test_course_without_lessons_has_zero_count(app, data):
    course = Course(
        company_id=data["alpha"].id,
        title="No lessons",
        level="beginner",
        status="published",
    )
    db.session.add(course)
    db.session.commit()
    row = search_courses("No lessons", "topic")[0]
    assert row["lesson_count"] == 0
    assert row["company_name"] == "Alpha"
    assert "lessons" not in row
    assert "Private learning content" not in str(row)


def test_catalog_uses_one_select_without_loading_lesson_bodies(app, data):
    for number in range(12):
        make_course(data["alpha"].id, f"Scale course {number}", status="published")
    db.session.commit()
    db.session.expunge_all()  # Do not let the fixture's identity cache hide lazy queries.
    with select_statements() as statements:
        rows = search_courses("Scale course", "topic")
    assert len(rows) == 12
    assert all(row["lesson_count"] == 1 for row in rows)
    assert len(statements) == 1
    assert "lesson.text" not in statements[0]


def test_company_search_uses_one_select(app, data):
    db.session.expunge_all()
    with select_statements() as statements:
        rows = search_companies("", "company")
    assert rows[0]["name"] == "Alpha"
    assert len(statements) == 1


def test_company_dashboard_keeps_score_offer_and_request_boundaries(app, data):
    learner = data["learner"]
    published, private = data["published"], data["private"]
    other_course = make_course(data["beta"].id, "Other company", status="published")
    for course, score in [(published, 60), (private, 90), (other_course, 100)]:
        db.session.add(
            Enrollment(user_id=learner.id, course_id=course.id, status="completed")
        )
        db.session.add(
            QuizAttempt(
                user_id=learner.id,
                quiz_id=course.lessons[0].quiz.id,
                score=score,
                passed=score >= 70,
            )
        )
    # A failed attempt still participates in best_score(), exactly as before.
    db.session.add(
        QuizAttempt(
            user_id=learner.id,
            quiz_id=published.lessons[0].quiz.id,
            score=40,
            passed=False,
        )
    )
    db.session.add_all(
        [
            Offer(
                company_id=data["alpha"].id,
                user_id=learner.id,
                course_id=published.id,
                text="One offer",
            ),
            Offer(
                company_id=data["beta"].id,
                user_id=learner.id,
                course_id=other_course.id,
                text="Other offer",
            ),
            AccessRequest(user_id=learner.id, course_id=private.id, status="pending"),
            AccessRequest(
                user_id=learner.id, course_id=other_course.id, status="pending"
            ),
        ]
    )
    db.session.commit()
    result = company_dashboard(data["alpha"])
    candidates = {row["course"].id: row for row in result["candidates"]}
    assert set(candidates) == {published.id, private.id}
    assert (
        candidates[published.id]["score"] == best_score(learner.id, published.id) == 60
    )
    assert candidates[private.id]["score"] == 90
    assert candidates[published.id]["offer_sent"] is True
    assert candidates[private.id]["offer_sent"] is False
    assert [row.course_id for row in result["requests"]] == [private.id]
    rows = {row["course"].id: row for row in result["courses"]}
    assert rows[published.id]["completers"][0]["score"] == 60
    assert rows[private.id]["enrolled"] == rows[private.id]["completed"] == 1


def test_company_dashboard_preserves_none_score(app, data):
    db.session.add(
        Enrollment(
            user_id=data["learner"].id,
            course_id=data["published"].id,
            status="completed",
        )
    )
    db.session.commit()
    result = company_dashboard(data["alpha"])
    assert result["candidates"][0]["score"] is None
    assert result["candidates"][0]["offer_sent"] is False


def test_empty_company_dashboard(app, data):
    assert company_dashboard(data["beta"]) == {
        "courses": [],
        "candidates": [],
        "requests": [],
    }


def test_company_dashboard_query_budget_does_not_grow_per_candidate(app, data):
    company_id, learner_id = data["alpha"].id, data["learner"].id
    for number in range(12):
        course = make_course(company_id, f"Dashboard {number}", status="published")
        db.session.add(
            Enrollment(user_id=learner_id, course_id=course.id, status="completed")
        )
        db.session.add(
            QuizAttempt(
                user_id=learner_id,
                quiz_id=course.lessons[0].quiz.id,
                score=80,
                passed=True,
            )
        )
    db.session.commit()
    db.session.expunge_all()
    company = db.session.get(Company, company_id)
    with select_statements() as statements:
        result = company_dashboard(company)
        # Include the fields templates actually read, not just construction of the dict.
        assert all(row["user"].display_name for row in result["candidates"])
        assert all(
            row["course"].lesson_count == 1
            for row in result["courses"]
            if row["course"].status == "published"
        )
    assert len(result["candidates"]) == 12
    assert len(statements) <= 7
