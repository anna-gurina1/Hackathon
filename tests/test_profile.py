from database.models import User
from tests.conftest import signup_confirmed


def person_client(app, email="ion@test.md"):
    client = app.test_client()
    signup_confirmed(client, {"type": "person", "first_name": "Ion", "last_name": "Popescu", "email": email})
    return client


def company_client(app, email="hr@acme.md"):
    client = app.test_client()
    signup_confirmed(client, {
        "type": "company", "company_name": "Acme", "description": "Old text", "email": email,
    })
    return client


def test_guest_is_sent_to_login(client):
    assert client.get("/account/edit").status_code == 302
    assert client.post("/account/edit", data={"first_name": "A", "last_name": "B"}).status_code == 302


def test_form_shows_current_values(app):
    page = person_client(app).get("/account/edit").data.decode()
    assert 'value="Ion"' in page and 'value="Popescu"' in page
    page = company_client(app).get("/account/edit").data.decode()
    assert 'value="Acme"' in page and "Old text" in page


def test_person_changes_name(app):
    client = person_client(app)
    response = client.post(
        "/account/edit", data={"first_name": "Ioan", "last_name": "Rusu"}, follow_redirects=True
    )
    assert b"Profile saved" in response.data
    with app.app_context():
        user = User.query.filter_by(email="ion@test.md").one()
        assert user.display_name == "Ioan Rusu"


def test_company_changes_name_and_description(app):
    client = company_client(app)
    client.post("/account/edit", data={"company_name": "Acme Group", "description": "New text"})
    with app.app_context():
        company = User.query.filter_by(email="hr@acme.md").one().company
        assert company.name == "Acme Group"
        assert company.description == "New text"


def test_company_can_clear_description(app):
    client = company_client(app)
    client.post("/account/edit", data={"company_name": "Acme", "description": "  "})
    with app.app_context():
        assert User.query.filter_by(email="hr@acme.md").one().company.description is None


def test_empty_name_is_rejected_and_nothing_changes(app):
    client = person_client(app)
    response = client.post("/account/edit", data={"first_name": "", "last_name": "Rusu"})
    assert b"Enter your first and last name" in response.data
    assert b'value="Rusu"' in response.data  # what was typed is kept in the form
    with app.app_context():
        assert User.query.filter_by(email="ion@test.md").one().display_name == "Ion Popescu"

    client = company_client(app)
    response = client.post("/account/edit", data={"company_name": " ", "description": "x"})
    assert b"Enter the company name" in response.data
    with app.app_context():
        assert User.query.filter_by(email="hr@acme.md").one().company.name == "Acme"


def test_too_long_values_are_cut(app):
    client = company_client(app)
    client.post("/account/edit", data={"company_name": "N" * 300, "description": "D" * 900})
    with app.app_context():
        company = User.query.filter_by(email="hr@acme.md").one().company
        assert len(company.name) == 120
        assert len(company.description) == 500


def test_email_cannot_be_changed(app):
    client = person_client(app)
    client.post("/account/edit", data={"first_name": "A", "last_name": "B", "email": "evil@test.md"})
    with app.app_context():
        assert User.query.filter_by(email="ion@test.md").count() == 1
        assert User.query.filter_by(email="evil@test.md").count() == 0


def test_one_user_cannot_change_another(app):
    ion = person_client(app, "ion@test.md")
    person_client(app, "ana@test.md")
    ion.post("/account/edit", data={"first_name": "Changed", "last_name": "Name"})
    with app.app_context():
        assert User.query.filter_by(email="ana@test.md").one().display_name == "Ion Popescu"


def test_account_pages_link_to_the_form(app):
    assert b"/account/edit" in person_client(app).get("/account").data
    assert b"/account/edit" in company_client(app).get("/account").data
