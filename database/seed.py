"""
Demo data: the companies and courses that are always on the site.

1. Automatically on every start of the server (core/__init__.py -> ensure_demo_data):
   missing demo companies / courses / learners are added. Nothing is deleted, and
   courses that already exist are not touched (so videos added in the studio stay).

2. Full reset (removes EVERY account and course, then adds only the demo data):
       python -m database.seed
   A copy of the old database is saved first as app.db.bak.

All demo accounts use the domain @bitwise.demo. Emails to these addresses are never
really sent: they are printed in the terminal where the server runs (backend/email.py).
So to log in as a demo company, use "Log in" with its email and copy the link from the terminal.
"""
import os
import shutil
from datetime import datetime, timedelta

from database import db
from database.models import (
    AccessRequest,
    CompanyProfile,
    Course,
    Enrollment,
    Lesson,
    PersonProfile,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    User,
)

DEMO_DOMAIN = "@bitwise.demo"
LEGACY_DEMO_EMAILS = ["demo-company@test.md"]  # old demo company (BuildRight), removed automatically


# ---------------------------------------------------------------------------
# Companies and their courses.
# Lesson: (title, text, quiz). Quiz: [(question, [(answer, is_correct), ...]), ...]
# ---------------------------------------------------------------------------

DEMO_COMPANIES = [
    {
        "email": "alliedtesting" + DEMO_DOMAIN,
        "name": "Allied Testing",
        "logo": "img/demo/alliedtesting.png",
        "description": (
            "Allied Testing is a leading global software quality assurance and testing consultancy "
            "specializing in the financial sector and capital markets. Founded in 2000, the company "
            "provides comprehensive QA automation, performance testing, and specialized IT consulting "
            "for elite investment banks, stock exchanges, and trading platforms worldwide."
        ),
        "course": {
            "title": "How to write a bug report developers can act on",
            "description": (
                "A 5-minute practical course for beginner testers. You will learn what a good bug report "
                "contains, why vague reports get ignored, and how to describe a problem so a developer "
                "can reproduce it on the first try."
            ),
            "topic": "Software testing",
            "profession": "QA engineer (software tester)",
            "outcome": (
                "After this course you will be able to write a clear bug report with a short title, exact "
                "steps to reproduce, the expected and the actual result, and a severity level."
            ),
            "level": "beginner",
            "duration": 5,
            "is_private": False,
        },
        "lessons": [
            (
                "Why vague bug reports get ignored",
                "\"The login doesn't work\" is not a bug report — it is a puzzle. The developer has to guess "
                "which page, which account, which browser and what \"doesn't work\" means. Most of the time "
                "they cannot reproduce it, mark it \"cannot reproduce\" and move on.\n\n"
                "A good report saves everybody's time: the developer can see the problem in one minute, "
                "and you do not have to answer ten follow-up questions.",
                [
                    ("What usually happens to a vague bug report?", [
                        ("The developer cannot reproduce it and it gets closed", True),
                        ("It is fixed faster because it is short", False),
                        ("It is automatically sent to the manager", False),
                    ]),
                    ("What is the main goal of a bug report?", [
                        ("To let a developer reproduce the problem on the first try", True),
                        ("To show that the tester found many bugs", False),
                        ("To describe how the tester feels about the product", False),
                    ]),
                ],
            ),
            (
                "The five parts of a good report",
                "1. Title — what is broken and where: \"Login button does nothing on Safari 17\".\n"
                "2. Steps to reproduce — numbered, exact, starting from a clear point: open page, type, click.\n"
                "3. Expected result — what should happen.\n"
                "4. Actual result — what happens instead. Add a screenshot or a short screen recording.\n"
                "5. Environment and severity — browser, device, app version, and how bad it is for users.",
                [
                    ("Which title is the most useful?", [
                        ("Login button does nothing on Safari 17", True),
                        ("Login broken!!!", False),
                        ("Problem", False),
                    ]),
                    ("What is the difference between expected and actual result?", [
                        ("Expected is what should happen, actual is what really happens", True),
                        ("They are the same thing written twice", False),
                        ("Expected is the tester's guess about the cause", False),
                    ]),
                ],
            ),
            (
                "Severity and the last check before you send",
                "Severity tells the team how urgent the bug is: Critical (users cannot work or lose money), "
                "Major (an important feature is broken, there is a workaround), Minor (small problem), "
                "Trivial (typo, cosmetic).\n\n"
                "Before sending, follow your own steps once more from the beginning. If you cannot reproduce "
                "the bug yourself, the developer will not be able to either.",
                [
                    ("Users cannot complete a payment at all. Which severity is it?", [
                        ("Critical", True),
                        ("Minor", False),
                        ("Trivial", False),
                    ]),
                    ("What should you do right before sending the report?", [
                        ("Repeat your own steps once more to make sure the bug reproduces", True),
                        ("Delete the screenshots to keep the report short", False),
                        ("Change the severity to Critical so it gets attention", False),
                    ]),
                ],
            ),
        ],
    },
    {
        "email": "victoriabank" + DEMO_DOMAIN,
        "name": "Victoriabank",
        "logo": "img/demo/victoriabank.png",
        "description": (
            "Victoriabank is one of the largest and most innovative commercial banks in Moldova, originally "
            "founded in 1989 as the country's first commercial banking institution. As part of Romania's "
            "Banca Transilvania Financial Group since 2018, it provides a comprehensive suite of digital and "
            "retail banking solutions to over 330,000 corporate and individual clients."
        ),
        "course": {
            "title": "Cyber hygiene for bank employees: protect your workstation in 5 minutes",
            "description": (
                "A 5-minute practical course for bank staff on everyday cybersecurity: strong passwords, "
                "phishing emails at work, and what to do when something looks suspicious. You will learn the "
                "habits that stop most attacks."
            ),
            "topic": "Cybersecurity",
            "profession": "Bank employee",
            "outcome": (
                "After this course you will be able to recognize a phishing email sent to employees, protect "
                "your accounts with strong passwords and two-step verification, and report a suspicious "
                "incident to the security team in the first minutes."
            ),
            "level": "beginner",
            "duration": 5,
            "is_private": True,
        },
        "lessons": [
            (
                "Spot a phishing email",
                "Phishing emails pretend to be a colleague, a manager, IT support or a client. Warning signs: "
                "urgency (\"do it in 10 minutes\"), a sender address that is almost right "
                "(victoriabamk.md), a link that shows a different address when you hover over it, an "
                "unexpected attachment, a request for a password or a payment.\n\n"
                "Rule: never enter your password from a link in an email. Open the system yourself.",
                [
                    ("Which of these is a typical sign of phishing?", [
                        ("An urgent request to log in through a link in the email", True),
                        ("An email from a colleague about a meeting you agreed on", False),
                        ("A newsletter you subscribed to", False),
                    ]),
                    ("An email asks you to confirm your password via a link. What do you do?", [
                        ("Do not click; open the system yourself and report the email", True),
                        ("Click the link but do not type anything", False),
                        ("Reply and ask if it is real", False),
                    ]),
                ],
            ),
            (
                "Passwords and two-step verification",
                "A strong password is long: a phrase of 4–5 random words is stronger and easier to remember "
                "than \"P@ssw0rd1\". Use a different password for every system and keep them in the "
                "password manager approved by the bank.\n\n"
                "Turn on two-step verification everywhere it is available: even if a password leaks, the "
                "attacker still cannot log in. Never tell anybody a one-time code — IT support will never ask for it.",
                [
                    ("Which password is the strongest?", [
                        ("river-lamp-orange-cloud-seven", True),
                        ("P@ssw0rd1", False),
                        ("victoria2024", False),
                    ]),
                    ("Someone from \"IT support\" calls and asks for your one-time code. What do you do?", [
                        ("Refuse and report the call to the security team", True),
                        ("Tell the code — IT support is allowed to know it", False),
                        ("Tell only half of the code", False),
                    ]),
                ],
            ),
            (
                "Something looks wrong? Report it in the first minutes",
                "Clicked a suspicious link, opened a strange attachment, or see unusual activity on your "
                "computer? Do not hide it and do not try to fix it yourself. Disconnect from the network if "
                "you can, and report to the security team right away — by phone or through the incident form.\n\n"
                "The first minutes matter most: a fast report can stop an attack before it spreads. "
                "Nobody is punished for reporting honestly. Lock your screen (Win + L) every time you leave your desk.",
                [
                    ("You clicked a phishing link by mistake. What is the right first step?", [
                        ("Report it to the security team immediately", True),
                        ("Wait and see if anything happens", False),
                        ("Delete the email so nobody knows", False),
                    ]),
                    ("What should you do every time you leave your desk?", [
                        ("Lock the screen", True),
                        ("Turn off the monitor only", False),
                        ("Nothing, the office is safe", False),
                    ]),
                ],
            ),
        ],
    },
    {
        "email": "fusionworks" + DEMO_DOMAIN,
        "name": "FusionWorks",
        "logo": "img/demo/fusionworks.png",
        "description": (
            "FusionWorks is an ISO-certified, AI-native software development company based in Chisinau, "
            "Moldova. Founded in 2011, it delivers full-cycle product engineering and staff augmentation "
            "services while actively organizing major regional technology events like Moldova DevCon for "
            "international clients across more than 20 countries."
        ),
        "course": {
            "title": "AI wrote the code, now what? Review, test and fix it like a developer",
            "description": (
                "A 15-minute practical course for junior developers. You will learn how to read code generated "
                "by an AI assistant, find hidden bugs and security problems, write tests for it, and decide "
                "what is safe to merge."
            ),
            "topic": "Software development with AI",
            "profession": "Junior software developer",
            "outcome": (
                "After this course you will be able to review AI-generated code critically, spot typical "
                "mistakes such as missing input checks, invented functions and unsafe queries, cover the "
                "result with a few tests, and explain your decision in a pull request."
            ),
            "level": "intermediate",
            "duration": 15,
            "is_private": False,
        },
        "lessons": [
            (
                "Treat AI code like code from a new colleague",
                "An AI assistant writes code fast and confidently — even when it is wrong. Treat its output "
                "like a pull request from a new team member: useful, but not trusted until reviewed.\n\n"
                "First, read it and explain it in your own words. If you cannot explain a line, you are not "
                "ready to merge it.",
                [
                    ("How should you treat code generated by an AI assistant?", [
                        ("Like a pull request from a new colleague: review before merging", True),
                        ("As correct, because AI does not make mistakes", False),
                        ("As a draft that never needs tests", False),
                    ]),
                    ("What is the first step of the review?", [
                        ("Read the code and explain what each part does", True),
                        ("Merge it and see if production breaks", False),
                        ("Ask the AI if its code is correct", False),
                    ]),
                ],
            ),
            (
                "Typical AI mistakes to look for",
                "1. Invented functions or libraries that do not exist (\"hallucinations\") — check the docs.\n"
                "2. Missing input checks: empty values, wrong types, very long strings.\n"
                "3. Unsafe database queries built by gluing strings — a door for SQL injection.\n"
                "4. Old or deprecated APIs.\n"
                "5. Code that works for the happy path only: no error handling, no edge cases.",
                [
                    ("The code calls a library function you cannot find in the documentation. What is it likely to be?", [
                        ("A hallucination: the AI invented it", True),
                        ("A secret feature, safe to use", False),
                        ("A typo in the documentation", False),
                    ]),
                    ("Why is building an SQL query by joining strings with user input dangerous?", [
                        ("It allows SQL injection", True),
                        ("It makes the query slower only", False),
                        ("It is not dangerous at all", False),
                    ]),
                ],
            ),
            (
                "Make it safe: inputs and queries",
                "Validate every input at the boundary: type, length, allowed values. Reject bad data with a "
                "clear error instead of letting it travel deeper.\n\n"
                "For databases, always use parameterized queries or the ORM: "
                "cursor.execute(\"SELECT * FROM users WHERE email = ?\", (email,)) — never "
                "f\"... WHERE email = '{email}'\". Never put secrets (API keys, passwords) into the code the AI wrote — use environment variables.",
                [
                    ("Which query is safe?", [
                        ("cursor.execute(\"SELECT * FROM users WHERE email = ?\", (email,))", True),
                        ("cursor.execute(f\"SELECT * FROM users WHERE email = '{email}'\")", False),
                        ("cursor.execute(\"SELECT * FROM users WHERE email = '\" + email + \"'\")", False),
                    ]),
                    ("Where should an API key live?", [
                        ("In an environment variable, not in the code", True),
                        ("In a comment at the top of the file", False),
                        ("In the README so the team can find it", False),
                    ]),
                ],
            ),
            (
                "Cover it with a few tests",
                "You do not need 100 tests. Write three kinds: one for the normal case, one for an edge case "
                "(empty list, zero, very long text) and one for bad input that must be rejected.\n\n"
                "Run them before and after you change the AI code. If a test you expected to pass fails, "
                "you just found the bug the AI hid.",
                [
                    ("Which set of tests is the minimum useful one?", [
                        ("Normal case, edge case and bad input", True),
                        ("Only the normal case", False),
                        ("No tests if the code looks clean", False),
                    ]),
                    ("A test you expected to pass fails on the AI code. What does it mean?", [
                        ("You probably found a real bug", True),
                        ("The test framework is broken", False),
                        ("You should delete the test", False),
                    ]),
                ],
            ),
            (
                "Decide and explain it in the pull request",
                "Merge only what you understand, what is tested and what passed review. In the pull request, "
                "write in 3–4 lines: what the code does, what you changed after the AI, which tests cover it, "
                "and anything the reviewer should look at.\n\n"
                "Saying \"AI generated it\" is not an explanation — you are the author now.",
                [
                    ("What belongs in the pull request description?", [
                        ("What the code does, what you changed and which tests cover it", True),
                        ("Only the words \"generated by AI\"", False),
                        ("Nothing, the code speaks for itself", False),
                    ]),
                    ("Who is responsible for AI-generated code after you merge it?", [
                        ("You, the developer who merged it", True),
                        ("The AI assistant", False),
                        ("Nobody", False),
                    ]),
                ],
            ),
        ],
    },
    {
        "email": "diez" + DEMO_DOMAIN,
        "name": "Diez",
        "logo": "img/demo/diez.png",
        "description": (
            "Diez is a leading independent online news media portal in Moldova, primarily tailored for the "
            "youth audience and students aged 15 to 39. Founded in April 2013, the platform delivers "
            "bilingual content in Romanian and Russian, focusing on socio-political events, education, "
            "career opportunities, and cultural development."
        ),
        "course": {
            "title": "Numbers don't lie, headlines do: check statistics before you publish",
            "description": (
                "A 10-minute practical course for junior journalists and editors. You will learn how to trace "
                "a statistic back to its source, spot misleading percentages and charts, and write a headline "
                "that does not distort the data."
            ),
            "topic": "Data journalism",
            "profession": "Junior journalist / news editor",
            "outcome": (
                "After this course you will be able to find the original source of a number, tell relative "
                "from absolute change, notice a misleading chart or a biased poll, and write a headline that "
                "matches what the data actually shows."
            ),
            "level": "intermediate",
            "duration": 10,
            "is_private": False,
        },
        "lessons": [
            (
                "Find where the number really comes from",
                "A number in a press release or a viral post is not a source. Follow it back to the original: "
                "the statistics office, the study, the survey report. Check who collected the data, when, "
                "how many people, and who paid for it.\n\n"
                "If you cannot find the original source, say so in the text — or do not publish the number.",
                [
                    ("A viral post quotes a statistic. What do you do first?", [
                        ("Find the original source of the number", True),
                        ("Publish it quickly before others do", False),
                        ("Trust it if many people shared it", False),
                    ]),
                    ("You cannot find the original source. What is the honest option?", [
                        ("Say it in the text or do not publish the number", True),
                        ("Round the number so it looks more official", False),
                        ("Attribute it to \"experts\"", False),
                    ]),
                ],
            ),
            (
                "Relative vs absolute change",
                "\"Risk doubled!\" sounds scary. But if it went from 1 in 10,000 to 2 in 10,000, the absolute "
                "change is tiny. Always give both: the percentage change and the real numbers behind it.\n\n"
                "Also watch the base: \"prices fell 50% after rising 100%\" means they are back where they started.",
                [
                    ("Risk went from 1 in 10,000 to 2 in 10,000. Which statement is complete?", [
                        ("Risk doubled, from 1 to 2 cases per 10,000 people", True),
                        ("Risk exploded by 100%!", False),
                        ("Risk did not change", False),
                    ]),
                    ("Why should you show absolute numbers next to a percentage?", [
                        ("So readers see how big the change really is", True),
                        ("To make the article longer", False),
                        ("Percentages are always wrong", False),
                    ]),
                ],
            ),
            (
                "Misleading charts and biased polls",
                "Charts lie quietly: a y-axis that does not start at zero makes a small change look huge; a "
                "chart that shows only a few chosen years hides the trend.\n\n"
                "Polls: check the sample size, who was asked (an online poll of a page's followers is not \"Moldovans\"), "
                "the margin of error, and the exact question — a leading question gives the answer it wants.",
                [
                    ("A bar chart's y-axis starts at 95 instead of 0. What is the risk?", [
                        ("A small difference looks much bigger than it is", True),
                        ("The chart becomes more accurate", False),
                        ("No risk at all", False),
                    ]),
                    ("An online poll of one Facebook page's followers says \"70% of Moldovans agree\". What is wrong?", [
                        ("The sample does not represent all Moldovans", True),
                        ("Nothing, 70% is a clear majority", False),
                        ("Online polls are always more precise", False),
                    ]),
                ],
            ),
            (
                "Write a headline that matches the data",
                "The headline is what most people read. It must say what the data shows — not more. Avoid "
                "\"proves\", \"all\", \"never\" when the study shows a link in one group.\n\n"
                "Check: would the researcher agree with your headline? Does it use the same numbers as the text? "
                "If the honest headline is boring, the story may be smaller than you thought — and that is fine.",
                [
                    ("A study finds a link between coffee and sleep problems in 200 students. Which headline is fair?", [
                        ("Study of 200 students links coffee to worse sleep", True),
                        ("Science proves coffee destroys your sleep", False),
                        ("Coffee causes insomnia in everyone", False),
                    ]),
                    ("What is a good final check for a headline?", [
                        ("Would the author of the data agree with it?", True),
                        ("Is it the most shocking option?", False),
                        ("Is it shorter than five words?", False),
                    ]),
                ],
            ),
        ],
    },
]

# Learners. "completed" = finished the course of that company (shown to the company as a candidate).
# "requested" = sent a request to the private course of that company (waits in the company account).
DEMO_LEARNERS = [
    {"email": "ana.popescu" + DEMO_DOMAIN, "first_name": "Ana", "last_name": "Popescu",
     "completed": ["alliedtesting" + DEMO_DOMAIN, "diez" + DEMO_DOMAIN], "score": 100},
    {"email": "ion.rusu" + DEMO_DOMAIN, "first_name": "Ion", "last_name": "Rusu",
     "completed": ["fusionworks" + DEMO_DOMAIN], "score": 90, "requested": ["victoriabank" + DEMO_DOMAIN]},
    {"email": "maria.ceban" + DEMO_DOMAIN, "first_name": "Maria", "last_name": "Ceban",
     "completed": ["alliedtesting" + DEMO_DOMAIN], "score": 80, "requested": ["victoriabank" + DEMO_DOMAIN]},
]


# ---------------------------------------------------------------------------

def _add_lessons(course, lessons):
    for order, (title, text, quiz_questions) in enumerate(lessons, start=1):
        lesson = Lesson(course_id=course.id, order=order, title=title, text=text)
        db.session.add(lesson)
        db.session.flush()
        quiz = Quiz(lesson=lesson, pass_score=70)
        db.session.add(quiz)
        for question_text, answers in quiz_questions:
            question = QuizQuestion(quiz=quiz, text=question_text)
            db.session.add(question)
            for answer_text, is_correct in answers:
                db.session.add(QuizAnswer(question=question, text=answer_text, is_correct=is_correct))


def _get_or_create_company(data):
    user = User.query.filter_by(email=data["email"]).first()
    if user is None:
        user = User(type="company", email=data["email"])
        # demo companies are on the top plan: they have many courses and private ones
        user.company = CompanyProfile(
            name=data["name"], description=data["description"], plan="monthly"
        )
        db.session.add(user)
        db.session.flush()
    if not user.avatar and data.get("logo"):  # the logo is a file in frontend/static, no Cloudinary needed
        user.avatar = "static:" + data["logo"]
    return user


def _get_or_create_course(company, data):
    info = data["course"]
    course = Course.query.filter_by(company_id=company.id, title=info["title"]).first()
    if course is None:
        course = Course(company_id=company.id, status="published", **info)
        course.update_language()
        db.session.add(course)
        db.session.flush()
        _add_lessons(course, data["lessons"])
    return course


def _get_or_create_learner(data, courses_by_company):
    user = User.query.filter_by(email=data["email"]).first()
    if user is not None:
        return
    user = User(type="person", email=data["email"])
    user.person = PersonProfile(first_name=data["first_name"], last_name=data["last_name"])
    db.session.add(user)
    db.session.flush()

    for days_ago, company_email in enumerate(data["completed"], start=1):
        course = courses_by_company.get(company_email)
        if course is None:
            continue
        finished = datetime.now() - timedelta(days=days_ago)
        db.session.add(Enrollment(
            user_id=user.id, course_id=course.id, status="completed",
            current_lesson=course.lesson_count, started_at=finished - timedelta(hours=1),
            completed_at=finished,
        ))
        for lesson in course.lessons:
            db.session.add(QuizAttempt(user_id=user.id, quiz_id=lesson.quiz.id,
                                       score=data["score"], passed=True, created_at=finished))

    for company_email in data.get("requested", []):
        course = courses_by_company.get(company_email)
        if course is not None:
            db.session.add(AccessRequest(user_id=user.id, course_id=course.id))


def _remove_legacy_demo():
    """The old demo company (BuildRight) and its courses are replaced by the new demo companies."""
    for email in LEGACY_DEMO_EMAILS:
        user = User.query.filter_by(email=email).first()
        if user is None:
            continue
        for course in Course.query.filter_by(company_id=user.id).all():
            db.session.delete(course)
        db.session.delete(user)
    db.session.flush()


def add_demo_data():
    """Adds whatever demo data is missing. Never deletes or changes existing courses
    (except the old BuildRight demo). Must run inside app.app_context()."""
    _remove_legacy_demo()
    courses_by_company = {}
    for data in DEMO_COMPANIES:
        company = _get_or_create_company(data)
        courses_by_company[data["email"]] = _get_or_create_course(company, data)
    for learner in DEMO_LEARNERS:
        _get_or_create_learner(learner, courses_by_company)
    db.session.commit()


def ensure_demo_data():
    """Called on every server start (core/__init__.py)."""
    add_demo_data()


def reset_to_demo():
    """Deletes ALL accounts, courses, progress and offers, then adds only the demo data.
    The tables themselves (and the migration version) stay."""
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()
    add_demo_data()


def seed():
    from core import create_app
    from core.config import BASE_DIR

    db_file = os.path.join(BASE_DIR, "app.db")
    if os.path.exists(db_file):
        shutil.copy(db_file, db_file + ".bak")
        print("Backup saved: app.db.bak")

    app = create_app()
    with app.app_context():
        reset_to_demo()

    print("Done. The database now has only the demo data.")
    print("Companies (log in with these emails, the login link is printed in the server terminal):")
    for data in DEMO_COMPANIES:
        private = " (private course)" if data["course"]["is_private"] else ""
        print(f"  {data['email']:<32} {data['name']}{private}")
    print("Learners:")
    for learner in DEMO_LEARNERS:
        print(f"  {learner['email']:<32} {learner['first_name']} {learner['last_name']}")


if __name__ == "__main__":
    seed()