import io
import json
import urllib.error

import pytest

from backend import ai_tips
from backend.ai_tips import AiUnavailable

CATEGORIES = [("goal", "Learning goal"), ("setup", "Show and setup")]


# ---------- backend/ai_tips.py ----------

def test_parse_accepts_json_in_code_fence_and_drops_unknown_keys():
    answer = '```json\n{"goal": " What will a barista pull? ", "setup": "Where is the grinder?", "other": "x"}\n```'
    result = ai_tips._parse(answer, ["goal", "setup"])
    assert result == {"goal": "What will a barista pull?", "setup": "Where is the grinder?"}


def test_parse_skips_bad_values_and_cuts_long_text():
    answer = '{"goal": 5, "setup": "' + "a" * 500 + '"}'
    result = ai_tips._parse(answer, ["goal", "setup"])
    assert "goal" not in result
    assert len(result["setup"]) == ai_tips.MAX_QUESTION_LENGTH


@pytest.mark.parametrize("answer", ["", "no json here", "[1, 2]", '{"goal": ""}', '{"unknown": "x"}'])
def test_parse_rejects_unusable_answers(answer):
    with pytest.raises(AiUnavailable):
        ai_tips._parse(answer, ["goal", "setup"])


def test_generate_puts_course_data_and_topics_into_the_prompt(monkeypatch):
    seen = {}

    def fake_call(system, user_text):
        seen["user_text"] = user_text
        return '{"goal": "Q1?", "setup": "Q2?"}'

    monkeypatch.setattr(ai_tips, "_call_api", fake_call)
    result = ai_tips.generate_category_questions(
        {"title": "Perfect espresso", "profession": "Barista", "topic": "", "level": "Beginner"},
        CATEGORIES,
    )

    assert result == {"goal": "Q1?", "setup": "Q2?"}
    assert "Perfect espresso" in seen["user_text"]
    assert "profession: Barista" in seen["user_text"]
    assert "goal: Learning goal" in seen["user_text"]
    assert "topic:" not in seen["user_text"].split("<course>")[1]  # empty fields are not sent


@pytest.mark.parametrize("provider", ["gemini", "anthropic"])
def test_missing_api_key_is_reported_as_unavailable(monkeypatch, provider):
    monkeypatch.setenv("AI_PROVIDER", provider)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AiUnavailable):
        ai_tips._call_api("system", "user")


def test_unknown_provider_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "nonsense")
    with pytest.raises(AiUnavailable):
        ai_tips._call_api("system", "user")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_gemini_request_and_answer(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)          # gemini is the default
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["key"] = request.get_header("X-goog-api-key")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {"candidates": [{"content": {"parts": [{"text": '{"goal": '}, {"text": '"Q1?"}'}]}}]}
        )

    monkeypatch.setattr(ai_tips.urllib.request, "urlopen", fake_urlopen)
    answer = ai_tips._call_api("SYSTEM TEXT", "USER TEXT")

    assert answer == '{"goal": "Q1?"}'
    assert seen["url"].endswith("/models/gemini-test-model:generateContent")
    assert "test-key" not in seen["url"]                      # the key goes in the header only
    assert seen["key"] == "test-key"
    sent = seen["body"]["contents"][0]["parts"][0]["text"]
    assert "SYSTEM TEXT" in sent and "USER TEXT" in sent


def test_gemini_answer_without_candidates_is_unavailable(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        ai_tips.urllib.request, "urlopen", lambda request, timeout: _FakeResponse({"candidates": []})
    )
    with pytest.raises(AiUnavailable):
        ai_tips._call_api("s", "u")


def test_gemini_http_error_is_unavailable(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def quota_exceeded(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b'{"error": {"message": "quota"}}')
        )

    monkeypatch.setattr(ai_tips.urllib.request, "urlopen", quota_exceeded)
    with pytest.raises(AiUnavailable):
        ai_tips._call_api("s", "u")


# ---------- POST /api/ai-suggestions ----------

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


def test_person_cannot_use_ai_suggestions(app):
    person = _signup_person(app, "ion@test.md")
    resp = person.post("/api/ai-suggestions", json={"topic": "Coffee"})
    assert resp.status_code == 403


def test_empty_form_is_rejected_before_calling_the_ai(app, monkeypatch):
    def must_not_be_called(fields, categories):
        raise AssertionError("the AI must not be called for an empty form")

    monkeypatch.setattr("backend.routes.courses.generate_category_questions", must_not_be_called)
    company = _signup_company(app, "Acme", "a@acme.md")

    resp = company.post(
        "/api/ai-suggestions",
        json={"title": "  ", "description": "", "topic": "", "profession": "", "outcome": ""},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "empty"


def test_company_gets_one_question_per_topic(app, monkeypatch):
    seen = {}

    def fake_generate(fields, categories):
        seen["fields"] = fields
        seen["keys"] = [key for key, _label in categories]
        return {key: f"AI question for {key}" for key in seen["keys"]}

    monkeypatch.setattr("backend.routes.courses.generate_category_questions", fake_generate)
    company = _signup_company(app, "Acme", "a@acme.md")

    resp = company.post(
        "/api/ai-suggestions",
        json={"title": "Espresso", "topic": "Coffee", "profession": "Barista", "level": "beginner"},
    )

    assert resp.status_code == 200
    questions = resp.get_json()["questions"]
    assert questions["goal"] == "AI question for goal"
    assert set(questions) == set(seen["keys"])
    assert "video_quality" not in seen["keys"]       # same topics as the side panel
    assert seen["fields"]["profession"] == "Barista"
    assert seen["fields"]["level"] == "Beginner"


def test_ai_failure_gives_503_and_does_not_break(app, monkeypatch):
    def broken(fields, categories):
        raise AiUnavailable("down")

    monkeypatch.setattr("backend.routes.courses.generate_category_questions", broken)
    company = _signup_company(app, "Acme", "a@acme.md")

    resp = company.post("/api/ai-suggestions", json={"topic": "Coffee"})
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "unavailable"


# ---------- POST /course/<id>/ai-suggestions (button on the course page) ----------

def _make_course(app, company_email, **fields):
    from database import db
    from database.models import Course, User

    with app.app_context():
        company = User.query.filter_by(email=company_email).one()
        data = dict(
            title="Espresso", description="", topic="", profession="", outcome="",
            level="beginner", knowledge_type="procedure", duration=5,
        )
        data.update(fields)
        course = Course(company_id=company.id, **data)
        db.session.add(course)
        db.session.commit()
        return course.id


def test_course_page_button_uses_the_saved_course(app, monkeypatch):
    seen = {}

    def fake_generate(fields, categories):
        seen["fields"] = fields
        return {key: f"AI question for {key}" for key, _label in categories}

    monkeypatch.setattr("backend.routes.courses.generate_category_questions", fake_generate)
    company = _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md", topic="Coffee", profession="Barista")

    resp = company.post(f"/course/{course_id}/ai-suggestions")

    assert resp.status_code == 200
    assert resp.get_json()["questions"]["goal"] == "AI question for goal"
    assert seen["fields"]["title"] == "Espresso"
    assert seen["fields"]["topic"] == "Coffee"
    assert seen["fields"]["profession"] == "Barista"
    assert seen["fields"]["level"] == "Beginner"


def test_course_page_button_with_nothing_filled_in_is_rejected(app, monkeypatch):
    def must_not_be_called(fields, categories):
        raise AssertionError("the AI must not be called when topic, profession, ... are empty")

    monkeypatch.setattr("backend.routes.courses.generate_category_questions", must_not_be_called)
    company = _signup_company(app, "Acme", "a@acme.md")
    course_id = _make_course(app, "a@acme.md")  # only a title

    resp = company.post(f"/course/{course_id}/ai-suggestions")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "empty"


def test_only_the_owner_can_ask_for_course_suggestions(app, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.courses.generate_category_questions", lambda fields, categories: {"goal": "Q?"}
    )
    _signup_company(app, "Acme", "a@acme.md")
    other = _signup_company(app, "Beta", "b@beta.md")
    person = _signup_person(app, "ion@test.md")
    course_id = _make_course(app, "a@acme.md", topic="Coffee")

    assert other.post(f"/course/{course_id}/ai-suggestions").status_code == 403
    assert person.post(f"/course/{course_id}/ai-suggestions").status_code == 403
