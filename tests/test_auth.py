from tests.conftest import find_login_link


def signup_person(client, email="ana@test.md"):
    return client.post("/signup", data={
        "type": "person", "first_name": "Test", "last_name": "User", "email": email,
    }, follow_redirects=True)


def test_home_page_opens(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"auth-signup" in response.data


def test_signup_person_logs_in(client):
    response = signup_person(client)
    assert b"Welcome, Test User" in response.data
    assert client.get("/account").status_code == 200


def test_signup_company(client):
    response = client.post("/signup", data={
        "type": "company", "company_name": "Acme", "email": "hr@acme.md",
    }, follow_redirects=True)
    assert b"Welcome, Acme" in response.data


def test_email_must_be_unique(client):
    signup_person(client)
    client.post("/logout")
    response = client.post("/signup", data={
        "type": "person", "first_name": "A", "last_name": "B", "email": "ana@test.md",
    })
    assert "auth=login" in response.headers["Location"]


def test_account_closed_for_guests(client):
    assert client.get("/account").status_code == 302


def test_login_link_works_once(client, capsys):
    signup_person(client)
    client.post("/logout")

    client.post("/login", data={"email": "ana@test.md"})
    link = find_login_link(capsys.readouterr().out)
    assert link

    response = client.get(link, follow_redirects=True)
    assert b"You are logged in" in response.data

    client.post("/logout")
    response = client.get(link)
    assert "auth=login" in response.headers["Location"]


def test_unknown_email_cannot_log_in(client):
    response = client.post("/login", data={"email": "nobody@test.md"})
    assert "auth=signup" in response.headers["Location"]


def test_404_page(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert b"Page not found" in response.data
