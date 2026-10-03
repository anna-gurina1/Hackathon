"""
Fake data for the frontend preview.
The objects have the SAME field names as the real models in database/models.py,
so the templates work with them exactly like with the real database.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

DEMO_VIDEO = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"

# Same as core/questions.py (labels for TYPES are made up for the preview)
LEVELS = {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Professional"}
TYPES = {
    "procedure": "Procedure",
    "practical_skill": "Practical skill",
    "decision_making": "Decision making",
    "experience": "Experience",
}
DURATIONS = [3, 5, 10, 15]


# ---------- Users ----------
class FakeUser(SimpleNamespace):
    is_authenticated = True

    @property
    def is_person(self):
        return self.type == "person"

    @property
    def is_company(self):
        return self.type == "company"

    @property
    def display_name(self):
        if self.is_company:
            return self.company.name
        return f"{self.person.first_name} {self.person.last_name}"

    @property
    def initials(self):
        words = self.display_name.split()
        return "".join(word[0] for word in words[:2]).upper()


class GuestUser:
    is_authenticated = False
    is_person = False
    is_company = False


def make_person(user_id, first_name, last_name, email):
    return FakeUser(id=user_id, type="person", email=email,
                    person=SimpleNamespace(first_name=first_name, last_name=last_name), company=None)


def make_company(user_id, name, email, description):
    return FakeUser(id=user_id, type="company", email=email, person=None,
                    company=SimpleNamespace(name=name, description=description))


northwind = make_company(1, "Northwind Coffee", "demo-company@test.md",
                         "Specialty coffee bars in Chișinău. We teach baristas the way we work behind the bar.")
greenleaf = make_company(2, "Greenleaf Pharmacy", "hello@greenleaf.md",
                         "Neighbourhood pharmacies with a focus on friendly, clear advice.")
ana = make_person(10, "Ana", "Rusu", "demo-person@test.md")
mihai = make_person(11, "Mihai", "Popescu", "mihai@test.md")
elena = make_person(12, "Elena", "Ciobanu", "elena@test.md")

ALL_USERS = {user.id: user for user in [northwind, greenleaf, ana, mihai, elena]}


# ---------- Courses, lessons, quizzes ----------
_next_id = [100]


def new_id():
    _next_id[0] += 1
    return _next_id[0]


class FakeCourse(SimpleNamespace):
    @property
    def lesson_count(self):
        return len(self.lessons)

    @property
    def yes_answer_ids(self):
        return {int(x) for x in self.yes_answers.split(",") if x}


def make_quiz(pass_score, questions):
    """questions = [("Question text", ["right answer", "wrong", "wrong"]), ...] — the first answer is correct."""
    quiz_questions = []
    for question_text, answer_texts in questions:
        answers = [SimpleNamespace(id=new_id(), text=text, is_correct=(index == 0))
                   for index, text in enumerate(answer_texts)]
        answers = answers[1:] + answers[:1] if len(answers) > 2 else answers  # so the right one isn't always first
        quiz_questions.append(SimpleNamespace(id=new_id(), text=question_text, category="goal", answers=answers))
    return SimpleNamespace(id=new_id(), pass_score=pass_score, questions=quiz_questions)


def make_lesson(order, title, question_id, text, video=True, quiz=None):
    return SimpleNamespace(id=new_id(), order=order, title=title, question_id=question_id,
                           video_filename="demo_espresso.mp4" if video else None, text=text, quiz=quiz)


espresso = FakeCourse(
    id=1, company=northwind, title="Pull a perfect espresso shot",
    description="A hands-on course from our head barista: from grinding beans to a balanced, sweet shot.",
    topic="Coffee", profession="Barista",
    outcome="Dial in the grinder, dose and tamp evenly, and pull a 25–30 second shot that tastes balanced.",
    level="beginner", knowledge_type="practical_skill", duration=5,
    is_private=False, invite_token="espresso-token-123", status="published", yes_answers="5",
    created_at=datetime.now() - timedelta(days=20),
    lessons=[
        make_lesson(1, "What a good espresso looks like", 1,
                    "A good shot runs 25–30 seconds.\nThe crema is hazel-brown and thick.\nIt tastes sweet, not sour or bitter.",
                    quiz=make_quiz(70, [
                        ("How long should a good espresso shot run?", ["25–30 seconds", "5–10 seconds", "60 seconds"]),
                        ("What colour should the crema be?", ["Hazel-brown", "White", "Almost black"]),
                    ])),
        make_lesson(2, "Dose, distribute and tamp", 2,
                    "Use 18 g of coffee.\nTap the portafilter to level the bed, then tamp straight down with even pressure.",
                    quiz=make_quiz(70, [
                        ("How much coffee do we dose for a double shot?", ["18 g", "8 g", "30 g"]),
                        ("Why do we level the coffee before tamping?", ["So water flows evenly", "It looks nicer", "To make it hotter"]),
                    ])),
        make_lesson(3, "Taste and fix your shot", 3,
                    "Sour → grind finer.\nBitter → grind coarser.\nChange one thing at a time.",
                    video=False,
                    quiz=make_quiz(70, [
                        ("Your shot tastes sour. What do you change first?", ["Grind finer", "Grind coarser", "Use more milk"]),
                        ("How many things should you change at once?", ["One", "Two", "Everything"]),
                    ])),
    ],
)

closing = FakeCourse(
    id=2, company=northwind, title="Closing shift checklist",
    description="Internal course for new staff: how we close the bar every night.",
    topic="Operations", profession="Barista", outcome="Close the bar safely and leave it ready for the morning team.",
    level="beginner", knowledge_type="procedure", duration=3,
    is_private=True, invite_token="Xk29-private-closing", status="published", yes_answers="",
    created_at=datetime.now() - timedelta(days=5),
    lessons=[
        make_lesson(1, "Clean the espresso machine", 1, "Backflush every group head with detergent.",
                    quiz=make_quiz(70, [("What do we use to backflush?", ["Detergent", "Milk", "Nothing"])])),
        make_lesson(2, "Cash and lock up", 2, "Count the cash twice and lock both doors.", video=False,
                    quiz=make_quiz(70, [("How many times do we count the cash?", ["Twice", "Once", "Never"])])),
    ],
)

latte_art = FakeCourse(
    id=3, company=northwind, title="Latte art: your first heart",
    description="Steam silky milk and pour a simple heart.",
    topic="Coffee", profession="Barista", outcome="Steam milk to a glossy microfoam and pour a heart.",
    level="intermediate", knowledge_type="practical_skill", duration=5,
    is_private=False, invite_token="latte-token", status="draft", yes_answers="",
    created_at=datetime.now() - timedelta(days=1),
    lessons=[make_lesson(1, "Why milk texture matters", 1, "Microfoam should look like wet paint.", quiz=None)],
)

pharmacy = FakeCourse(
    id=4, company=greenleaf, title="Explaining a prescription to a customer",
    description="How to explain dosage and side effects clearly and kindly.",
    topic="Customer service", profession="Pharmacist", outcome="Explain any prescription in under two minutes.",
    level="advanced", knowledge_type="experience", duration=10,
    is_private=False, invite_token="pharma-token", status="published", yes_answers="",
    created_at=datetime.now() - timedelta(days=12),
    lessons=[make_lesson(1, "Start with the why", 1, "Tell the customer what the medicine is for first.",
                         quiz=make_quiz(50, [("What do you explain first?", ["What it is for", "The price", "The brand"])]))],
)

ALL_COURSES = {course.id: course for course in [espresso, closing, latte_art, pharmacy]}


# ---------- Questions for the builder (like core/questions.py) ----------
QUESTIONS = [
    {"id": 1, "text": "What result should the learner get at the end?", "hint": "Show the finished result on camera for 5 seconds.",
     "category": "goal", "time": 30, "priority": 1, "answer_type": "media", "if_yes": [], "only_after": None},
    {"id": 2, "text": "Show how you prepare your workplace before you start.", "hint": "Film from above so the tools are visible.",
     "category": "setup", "time": 60, "priority": 1, "answer_type": "media", "if_yes": [], "only_after": None},
    {"id": 3, "text": "Do it once from start to finish, slowly.", "hint": "Say out loud what you are doing.",
     "category": "demonstration", "time": 90, "priority": 1, "answer_type": "media", "if_yes": [], "only_after": None},
    {"id": 5, "text": "Is there a common mistake beginners make here?", "hint": "",
     "category": "mistake", "time": 0, "priority": 2, "answer_type": "yes_no", "if_yes": [6], "only_after": None},
    {"id": 6, "text": "Show the most common mistake and how to fix it.", "hint": "Do it wrong on purpose, then the right way.",
     "category": "mistake", "time": 60, "priority": 2, "answer_type": "media", "if_yes": [], "only_after": 5},
    {"id": 7, "text": "How do you check that the work is done right?", "hint": "",
     "category": "verification", "time": 45, "priority": 2, "answer_type": "media", "if_yes": [], "only_after": None},
]

CATEGORIES = {"goal": "Goal", "setup": "Setup", "demonstration": "Demonstration", "explanation": "Explanation",
              "reasoning": "Reasoning", "mistake": "Mistake", "example": "Example", "exception": "Exception",
              "verification": "Verification", "video_quality": "Video quality"}

QUIZ_TEMPLATES = {
    "goal": ["What is the main result of this step?", "How do you know the result is good?"],
    "setup": ["What do you need to prepare before you start?", "Which tool is used first?"],
    "demonstration": ["What is the first step?", "What comes right after …?"],
}


# ---------- Enrollments, offers (Ana is the demo person) ----------
class FakeEnrollment(SimpleNamespace):
    @property
    def progress_percent(self):
        if self.status == "completed":
            return 100
        passed_lessons = self.current_lesson - 1
        return round(passed_lessons * 100 / max(self.course.lesson_count, 1))


def make_enrollment(user, course, current_lesson, status="in_progress", days_ago=3):
    completed_at = datetime.now() - timedelta(days=days_ago - 1) if status == "completed" else None
    return FakeEnrollment(id=new_id(), user_id=user.id, course=course, course_id=course.id, status=status,
                          current_lesson=current_lesson, started_at=datetime.now() - timedelta(days=days_ago),
                          completed_at=completed_at)


def make_starting_state():
    """Everything that changes while you click around. /_preview/reset brings it back."""
    return {
        # Ana's enrollments by course id
        "enrollments": {
            1: make_enrollment(ana, espresso, current_lesson=2),
            4: make_enrollment(ana, pharmacy, current_lesson=2, status="completed", days_ago=8),
        },
        "offers": [
            SimpleNamespace(company=greenleaf, user_id=ana.id, course=pharmacy,
                            text="Hi Ana! You did great in our course. Would you like to come in for a trial day next week?",
                            created_at=datetime.now() - timedelta(days=2)),
        ],
        # People who finished Northwind courses
        "candidates": [
            {"user": mihai, "course": espresso, "score": 100, "completed_at": datetime.now() - timedelta(days=1), "offer_sent": False},
            {"user": elena, "course": closing, "score": 85, "completed_at": datetime.now() - timedelta(days=4), "offer_sent": True},
        ],
    }
