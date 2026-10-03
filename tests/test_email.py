import smtplib

from backend.email import send_email


class FakeExecutor:
    """Collects the jobs instead of running them in a thread."""

    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args):
        self.jobs.append((fn, args))


class FakeSMTP:
    sent = []
    fail = False

    def __init__(self, host, port, timeout=None):
        if FakeSMTP.fail:
            raise OSError("no connection")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def smtp_app(app):
    app.config.update(
        MAIL_SERVER="smtp.test", MAIL_PORT=587, MAIL_USE_TLS=True, MAIL_USE_SSL=False,
        MAIL_USERNAME="u", MAIL_PASSWORD="p", MAIL_FROM="noreply@test.md", MAIL_BACKGROUND=True,
    )
    FakeSMTP.sent, FakeSMTP.fail = [], False
    return app


def test_without_mail_server_the_email_is_printed(app, capsys):
    with app.app_context():
        assert send_email("a@test.md", "Hello", "Body text") is True
    out = capsys.readouterr().out
    assert "EMAIL to: a@test.md" in out and "Body text" in out


def test_sending_is_handed_to_a_background_worker(app, monkeypatch):
    smtp_app(app)
    executor = FakeExecutor()
    monkeypatch.setattr("backend.email._executor", executor)
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    with app.app_context():
        assert send_email("a@test.md", "Hello", "Body") is True

    assert FakeSMTP.sent == []        # the request did not talk to the mail server
    assert len(executor.jobs) == 1    # the work is waiting for a worker thread

    fn, args = executor.jobs[0]       # what the worker thread does later
    assert fn(*args) is True
    message = FakeSMTP.sent[0]
    assert message["To"] == "a@test.md"
    assert message["Subject"] == "Hello"
    assert message["From"] == "noreply@test.md"


def test_failed_delivery_does_not_break_the_page(app, monkeypatch):
    smtp_app(app)
    executor = FakeExecutor()
    monkeypatch.setattr("backend.email._executor", executor)
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    FakeSMTP.fail = True

    with app.app_context():
        assert send_email("a@test.md", "Hello", "Body") is True   # the page already got "ok"
    fn, args = executor.jobs[0]
    assert fn(*args) is False   # the worker only logs the error


def test_background_can_be_turned_off(app, monkeypatch):
    smtp_app(app)
    app.config["MAIL_BACKGROUND"] = False
    executor = FakeExecutor()
    monkeypatch.setattr("backend.email._executor", executor)
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    with app.app_context():
        assert send_email("a@test.md", "Hello", "Body") is True
    assert executor.jobs == []
    assert len(FakeSMTP.sent) == 1
