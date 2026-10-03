"""
Demo data for local development and testing.

Run from the project root:
    python -m database.seed

Resets the database (drop_all + create_all) and adds:
- one demo company account
- one demo person account
- one published, public course with 3 lessons, each with a 2-question quiz
- one published, private course (accessible only via its invite link)

There are no passwords: to log in locally, use "Log in" with the printed
emails below — the one-time login link is printed to this console
(MAIL_SERVER is empty in development, see core/config.py).
"""

from core import create_app
from database import db
from database.models import (
    CompanyProfile,
    Course,
    Lesson,
    PersonProfile,
    Quiz,
    QuizAnswer,
    QuizQuestion,
    User,
)

DEMO_COMPANY_EMAIL = "demo-company@test.md"
DEMO_PERSON_EMAIL = "demo-person@test.md"


def _add_quiz(lesson, questions):
    """questions: list of (question_text, category, [(answer_text, is_correct), ...])"""
    quiz = Quiz(lesson=lesson, pass_score=70)
    db.session.add(quiz)
    for q_text, category, answers in questions:
        question = QuizQuestion(quiz=quiz, text=q_text, category=category)
        db.session.add(question)
        for a_text, is_correct in answers:
            db.session.add(QuizAnswer(question=question, text=a_text, is_correct=is_correct))


def add_demo_data():
    """Adds the demo company, demo person and two demo courses to the current database.
    Does not delete anything. Must run inside app.app_context().
    Returns (public_course, private_course)."""
    # --- Demo company -------------------------------------------------
    company = User.query.filter_by(email=DEMO_COMPANY_EMAIL).first()
    if company is None:
        company = User(type="company", email=DEMO_COMPANY_EMAIL)
        company.company = CompanyProfile(
            name="BuildRight Construction",
            description="A mid-size construction company specializing in residential concrete work.",
        )
        db.session.add(company)

    # --- Demo person ----------------------------------------------------
    if User.query.filter_by(email=DEMO_PERSON_EMAIL).first() is None:
        person = User(type="person", email=DEMO_PERSON_EMAIL)
        person.person = PersonProfile(first_name="Demo", last_name="Learner")
        db.session.add(person)

    db.session.flush()  # assign ids before using company.id as a foreign key

    # --- Public course: 3 lessons with quizzes --------------------------
    course = Course(
        company_id=company.id,
        title="How to check rebar before concreting",
        description=(
            "A short, practical course on inspecting rebar placement before the "
            "concrete pour — what to check, common mistakes, and how to verify the result."
        ),
        topic="Concrete and reinforcement",
        profession="Construction worker",
        outcome="Confidently inspect rebar placement and catch mistakes before concreting.",
        level="beginner",
        knowledge_type="procedure",
        duration=5,
        is_private=False,
        status="published",
    )
    db.session.add(course)
    db.session.flush()

    lesson1 = Lesson(
        course_id=course.id,
        order=1,
        title="Why checking rebar matters",
        text=(
            "Once concrete is poured, the rebar underneath is hidden. Any mistake in "
            "placement, spacing or cover becomes very costly to fix — often requiring "
            "the concrete to be broken out. A quick check before the pour catches "
            "problems while they are still easy and cheap to correct.\n\n"
            "This is why, on every job, a qualified site supervisor or quality "
            "inspector signs off on the rebar before the concrete truck is called."
        ),
    )
    db.session.add(lesson1)
    db.session.flush()
    _add_quiz(lesson1, [
        (
            "Why is it important to check rebar before concreting?",
            "goal",
            [
                ("Because mistakes become hidden and costly to fix once concrete is poured", True),
                ("Because rebar is expensive", False),
                ("Because it saves time", False),
            ],
        ),
        (
            "Who should check the rebar before concreting starts?",
            "goal",
            [
                ("A qualified site supervisor or quality inspector", True),
                ("Only the person who installed it", False),
                ("No one — it is optional", False),
            ],
        ),
    ])

    lesson2 = Lesson(
        course_id=course.id,
        order=2,
        title="What to check: spacing, cover and ties",
        text=(
            "Three things to verify on every check:\n\n"
            "1. Spacing — bars should be at the distance shown on the drawing, "
            "held in place by spacer chairs and tie wire so they don't shift during the pour.\n"
            "2. Cover — the distance from the rebar to the formwork or ground surface, "
            "which protects the steel from corrosion. Measure it, don't estimate it by eye.\n"
            "3. Ties — every intersection should be tied firmly enough that the bars "
            "don't move when you push on them by hand."
        ),
    )
    db.session.add(lesson2)
    db.session.flush()
    _add_quiz(lesson2, [
        (
            "What should you measure to confirm correct concrete cover?",
            "demonstration",
            [
                ("The distance from the rebar to the formwork or surface", True),
                ("The length of the rebar", False),
                ("The weight of the rebar", False),
            ],
        ),
        (
            "What keeps rebar bars at the correct spacing during the pour?",
            "demonstration",
            [
                ("Spacer chairs and tie wire", True),
                ("Gravity", False),
                ("The weight of the concrete", False),
            ],
        ),
    ])

    lesson3 = Lesson(
        course_id=course.id,
        order=3,
        title="Common mistakes and how to catch them",
        text=(
            "The most common mistake is loose ties: a bar that looks fine by eye can "
            "still shift out of position once concrete starts flowing around it. "
            "Push on a sample of ties by hand across the whole area, not just a few "
            "near the access point.\n\n"
            "If you find a mistake, fix it before the concrete truck arrives — once "
            "the pour starts, it is too late to adjust anything underneath."
        ),
    )
    db.session.add(lesson3)
    db.session.flush()
    _add_quiz(lesson3, [
        (
            "What is a common mistake when tying rebar?",
            "mistake",
            [
                ("Leaving ties loose so bars shift during the pour", True),
                ("Using too many ties", False),
                ("Tying bars too tightly", False),
            ],
        ),
        (
            "What should you do if you find a mistake during the final check?",
            "verification",
            [
                ("Fix it before the concrete truck arrives", True),
                ("Ignore it if it looks small", False),
                ("Note it and fix it after pouring", False),
            ],
        ),
    ])

    # --- Private course (invite-link only) -------------------------------
    private_course = Course(
        company_id=company.id,
        title="New hire safety briefing",
        description="A short internal briefing for new site staff. Shared by invite link only.",
        topic="Site safety",
        profession="Construction worker",
        outcome="Know the basic safety rules before stepping on site for the first time.",
        level="beginner",
        knowledge_type="procedure",
        duration=3,
        is_private=True,
        status="published",
    )
    db.session.add(private_course)
    db.session.flush()

    pc_lesson = Lesson(
        course_id=private_course.id,
        order=1,
        title="Before you step on site",
        text=(
            "Always wear your hard hat, hi-vis vest and safety boots before entering "
            "the site. Report to the site supervisor first — do not walk in unannounced."
        ),
    )
    db.session.add(pc_lesson)
    db.session.flush()
    _add_quiz(pc_lesson, [
        (
            "What must you wear before entering the site?",
            "goal",
            [
                ("Hard hat, hi-vis vest and safety boots", True),
                ("Just a hard hat", False),
                ("Whatever is comfortable", False),
            ],
        ),
    ])

    db.session.commit()
    return course, private_course


def ensure_demo_data():
    """Adds the demo courses once, so a fresh database always has a course to try.
    Called from create_app(). Returns True if the data was added now."""
    company = User.query.filter_by(email=DEMO_COMPANY_EMAIL).first()
    if company is not None and Course.query.filter_by(company_id=company.id).first() is not None:
        return False
    add_demo_data()
    return True


def seed():
    """Full reset: drops all tables, creates them again and adds the demo data."""
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()
        course, private_course = add_demo_data()

        print("Seed complete.")
        print(f"  Company login:  {DEMO_COMPANY_EMAIL}")
        print(f"  Person login:   {DEMO_PERSON_EMAIL}")
        print(f"  Public course:  /course/{course.id}")
        print(f"  Private course: /course/private/{private_course.invite_token}")
        print("Use 'Log in' with either email — the one-time link prints to this console.")


if __name__ == "__main__":
    seed()