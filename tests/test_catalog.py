"""Catalog refinements must not expose drafts or depend on browser JavaScript."""

import pytest

from database import db
from database.models import Course


def test_home_shows_published_courses_but_not_drafts(app, data):
    html = app.test_client().get("/").get_data(as_text=True)
    assert data["published"].title in html
    assert data["assigned"].title not in html
    assert data["unassigned"].title not in html
    assert "data-theme-toggle" in html
    assert 'id="main-content"' in html


def test_catalog_is_rendered_without_javascript(app, data):
    response = app.test_client().get("/explore")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert data["published"].title in html
    assert data["assigned"].title not in html
    assert 'method="get"' in html


def test_topic_filter_matches_exact_existing_topic(app, data):
    data["published"].topic = "Web development"
    data["private"].topic = "Design"
    data["assigned"].topic = "Unpublished topic"
    db.session.commit()
    client = app.test_client()
    results = client.get("/api/search?topic=Web+development").get_json()
    assert [item["id"] for item in results] == [data["published"].id]
    assert results[0]["topic"] == "Web development"
    html = client.get("/explore?topic=Web+development").get_data(as_text=True)
    assert data["published"].title in html
    assert data["private"].title not in html
    assert "Unpublished topic" not in html


def test_topic_filter_combines_with_query_and_language(app, data):
    course = data["published"]
    course.topic = "Python"
    course.language = "ru"
    db.session.commit()
    client = app.test_client()
    assert len(client.get("/api/search?topic=Python&lang=ru&q=Public").get_json()) == 1
    assert client.get("/api/search?topic=Python&lang=en").get_json() == []
    assert client.get("/api/search?topic=Python&q=missing").get_json() == []
    assert client.get("/api/search?topic=Pyth").get_json() == []


def test_catalog_keeps_private_listing_but_not_draft(app, data):
    client = app.test_client()
    ids = {item["id"] for item in client.get("/api/search").get_json()}
    assert data["private"].id in ids  # Existing approval-based catalog behavior.
    assert data["assigned"].id not in ids
    assert data["unassigned"].id not in ids
    assert client.get("/course/" + str(data["assigned"].id)).status_code in (403, 404)


def test_unknown_search_mode_falls_back_for_get_form(app, data):
    html = app.test_client().get("/explore?by=invalid").get_data(as_text=True)
    assert data["published"].title in html
    assert 'value="topic" checked' in html


def test_empty_search_offers_reset(app):
    html = app.test_client().get("/explore?q=nothing").get_data(as_text=True)
    assert "No matching courses" in html
    assert "Reset filters" in html


def test_company_mode_server_rendering(app, data):
    html = app.test_client().get("/explore?by=company&q=Alpha").get_data(as_text=True)
    assert "Alpha" in html
    assert "result-company" in html
    assert data["assigned"].title not in html


def test_user_text_is_escaped_in_catalog(app, data):
    data["published"].title = '<script>alert("test")</script>'
    data["published"].topic = "<b>Topic</b>"
    db.session.commit()
    html = app.test_client().get("/explore").get_data(as_text=True)
    assert "&lt;script&gt;" in html
    assert "<script>alert(" not in html
    assert "&lt;b&gt;Topic&lt;/b&gt;" in html


def test_home_limits_featured_courses(app, data):
    for number in range(6):
        db.session.add(
            Course(
                company_id=data["alpha"].id,
                title=f"Extra {number}",
                level="beginner",
                status="published",
            )
        )
    db.session.commit()
    html = app.test_client().get("/").get_data(as_text=True)
    assert html.count('class="card course-card catalog-card"') == 3


def test_empty_company_search_has_company_message(app):
    html = app.test_client().get("/explore?by=company&q=Missing").get_data(as_text=True)
    assert "<h3>No matching companies</h3>" in html
    assert "<h3>No matching courses</h3>" not in html


@pytest.mark.parametrize("available_topic", [None, "Design"])
def test_missing_topic_from_url_stays_visible_in_filter(app, data, available_topic):
    data["published"].topic = available_topic
    db.session.commit()
    html = app.test_client().get("/explore?topic=RemovedTopic").get_data(as_text=True)
    assert "data-topic-filter" in html
    assert '<option value="RemovedTopic" selected>RemovedTopic</option>' in html
    assert "No matching courses" in html


def test_missing_topic_label_is_escaped(app, data):
    label = "<img src=x onerror=alert(1)>"
    html = (
        app.test_client()
        .get("/explore", query_string={"topic": label})
        .get_data(as_text=True)
    )
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
