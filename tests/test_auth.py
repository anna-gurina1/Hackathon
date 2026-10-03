from datetime import datetime, timedelta

from database import db
from database.models import EmailThrottle, User
from tests.conftest import find_confirm_link, find_login_link, signup_confirmed

PERSON = {"type": "person", "first_name": "Test", "last_name": "User", "email": "ana@test.md"}


def signup_person(client, email="ana@test.md"):
    """Full sign-up: fill the form, open the link from the email."""
    return signup_confirmed(client, dict(PERSON, email=email), follow_redirects=True)


def emails_sent(text):
    return text.count("EMAIL to:")


def test_home_page_opens(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'action="/signup"' in response.data


# ---------- sign-up with email confirmation ----------

def test_signup_sends_link_and_creates_nothing_yet(app, client, capsys):
    response = client.post("/signup", data=PERSON, follow_redirects=True)
    out = capsys.readouterr().out
    assert b"confirmation link" in response.data
    assert "EMAIL to: ana@test.md" in out
    assert find_confirm_link(out)
    with app.app_context():
        assert User.query.count() == 0           # nobody is created before the link is opened
    assert client.get("/account").status_code == 302  # and nobody is logged in


def test_confirm_link_creates_account_and_logs_in(app, client, capsys):
    client.post("/signup", data=PERSON)
    link = find_confirm_link(capsys.readouterr().out)

    response = client.get(link, follow_redirects=True)
    assert b"Welcome, Test User" in response.data
    assert client.get("/account").status_code == 200
    with app.app_context():
        assert User.query.count() == 1


def test_signup_company_after_confirmation(client):
    response = signup_confirmed(client, {
        "type": "company", "company_name": "Acme", "description": "Builders", "email": "hr@acme.md",
    }, follow_redirects=True)
    assert b"Welcome, Acme" in response.data


def test_confirm_link_second_use_does_not_log_in(app, client, capsys):
    client.post("/signup", data=PERSON)
    link = find_confirm_link(capsys.readouterr().out)
    client.get(link)
    client.post("/logout")

    response = client.get(link)
    assert "auth=login" in response.headers["Location"]
    assert client.get("/account").status_code == 302
    with app.app_context():
        assert User.query.count() == 1


def test_confirm_link_garbage_is_rejected(client):
    response = client.get("/signup/confirm/not-a-real-token")
    assert "auth=signup" in response.headers["Location"]


def test_confirm_link_expires(client, capsys, monkeypatch):
    client.post("/signup", data=PERSON)
    link = find_confirm_link(capsys.readouterr().out)
    monkeypatch.setattr("backend.routes.site_auth.SIGNUP_LINK_MAX_AGE", -1)
    response = client.get(link)
    assert "auth=signup" in response.headers["Location"]
    assert client.get("/account").status_code == 302


def test_login_link_is_not_a_signup_link(client, capsys):
    signup_person(client)
    client.post("/logout")
    capsys.readouterr()
    with client.application.app_context():
        db.session.query(EmailThrottle).delete()
        db.session.commit()
    client.post("/login", data={"email": "ana@test.md"})
    login_path = find_login_link(capsys.readouterr().out)
    token = login_path.rsplit("/", 1)[1]
    response = client.get(f"/signup/confirm/{token}")
    assert "auth=signup" in response.headers["Location"]


def test_signup_validation_sends_nothing(client, capsys):
    client.post("/signup", data={"type": "person", "first_name": "", "last_name": "", "email": "a@test.md"})
    client.post("/signup", data={"type": "person", "first_name": "A", "last_name": "B", "email": "nonsense"})
    client.post("/signup", data={"type": "company", "company_name": "", "email": "c@test.md"})
    assert emails_sent(capsys.readouterr().out) == 0


def test_email_must_be_unique(client, capsys):
    signup_person(client)
    client.post("/logout")
    capsys.readouterr()
    response = client.post("/signup", data=PERSON)
    assert "auth=login" in response.headers["Location"]
    assert emails_sent(capsys.readouterr().out) == 0


def test_account_closed_for_guests(client):
    assert client.get("/account").status_code == 302


# ---------- login ----------

def test_login_link_works_once(client, capsys):
    signup_person(client)
    client.post("/logout")
    capsys.readouterr()

    client.post("/login", data={"email": "ana@test.md"})
    link = find_login_link(capsys.readouterr().out)
    assert link

    response = client.get(link, follow_redirects=True)
    assert b"You are logged in" in response.data

    client.post("/logout")
    response = client.get(link)
    assert "auth=login" in response.headers["Location"]


def test_unknown_email_cannot_log_in(client, capsys):
    response = client.post("/login", data={"email": "nobody@test.md"})
    assert "auth=signup" in response.headers["Location"]
    assert emails_sent(capsys.readouterr().out) == 0


# ---------- pause between emails to one address ----------

def test_login_form_cannot_spam_one_address(app, client, capsys):
    signup_person(client)
    client.post("/logout")
    capsys.readouterr()

    for _ in range(4):
        client.post("/login", data={"email": "ana@test.md"})
    assert emails_sent(capsys.readouterr().out) == 1


def test_pause_message_says_how_long_to_wait(client):
    signup_person(client)
    client.post("/logout")
    client.post("/login", data={"email": "ana@test.md"})
    response = client.post("/login", data={"email": "ana@test.md"}, follow_redirects=True)
    assert b"You can request another in" in response.data


def test_login_works_again_after_the_pause(app, client, capsys):
    signup_person(client)
    client.post("/logout")
    client.post("/login", data={"email": "ana@test.md"})
    capsys.readouterr()

    with app.app_context():  # pretend the last email was sent 61 seconds ago
        row = db.session.get(EmailThrottle, "auth:ana@test.md")
        row.sent_at = datetime.utcnow() - timedelta(seconds=61)
        db.session.commit()

    client.post("/login", data={"email": "ana@test.md"})
    assert emails_sent(capsys.readouterr().out) == 1


def test_pause_is_per_address_and_case_insensitive(client, capsys):
    signup_person(client, "ana@test.md")
    client.post("/logout")
    signup_person(client, "ion@test.md")
    client.post("/logout")
    capsys.readouterr()

    client.post("/login", data={"email": "ana@test.md"})
    client.post("/login", data={"email": "ANA@test.md"})   # same address
    client.post("/login", data={"email": "ion@test.md"})   # another address
    assert emails_sent(capsys.readouterr().out) == 2


def test_signup_form_cannot_spam_one_address(client, capsys):
    for _ in range(3):
        client.post("/signup", data=PERSON)
    assert emails_sent(capsys.readouterr().out) == 1


def test_404_page(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_login_before_confirming_says_so(client):
    client.post("/signup", data={"type": "person", "first_name": "Ana", "last_name": "G",
                                 "email": "new@test.md"})
    response = client.post("/login", data={"email": "new@test.md"}, follow_redirects=True)
    assert b"You have not confirmed your email yet" in response.data
    response = client.post("/signup", data={"type": "person", "first_name": "Ana", "last_name": "G",
                                            "email": "new@test.md"}, follow_redirects=True)
    assert b"confirmation link" in response.data
