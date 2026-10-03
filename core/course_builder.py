"""Choosing the interview questions for the master.

The master sets the learner level, the type of knowledge and the video length.
select_questions() picks questions from core/questions.py so that:
  1. every useful teaching category gets at least one question (goal, demonstration, mistake, ...);
  2. the total answer time fits into the chosen duration;
  3. follow-up questions appear only after the master answered "yes" to their yes/no question.
"""
from core.questions import CATEGORIES, DURATION_GUIDANCE, DURATIONS, QUESTIONS

CATEGORY_ORDER = list(CATEGORIES)


def category_label(category):
    """'mistake' -> 'Common mistakes'."""
    return CATEGORIES.get(category, category)


def _guidance(duration):
    """Settings for the duration; an unknown value uses the next longer supported one."""
    if duration not in DURATION_GUIDANCE:
        longer = [d for d in DURATIONS if d >= duration]
        duration = min(longer) if longer else max(DURATIONS)
    return duration, DURATION_GUIDANCE[duration]


def _sort_key(question):
    return (question["priority"], question["id"])


def select_questions(level, knowledge_type, duration, yes_answers=None):
    """Return the list of question dicts for the master, in teaching order.

    level           -- key of LEVELS, e.g. "beginner"
    knowledge_type  -- key of TYPES, e.g. "procedure"
    duration        -- minutes, one of DURATIONS (3, 5, 10, 15)
    yes_answers     -- ids of yes/no questions the master answered "yes"
    """
    yes_answers = set(yes_answers or [])
    duration, guidance = _guidance(duration)
    max_time = duration * 60
    preferred = guidance["preferred_categories"]

    pool = sorted(
        (
            q for q in QUESTIONS
            if level in q["levels"]
            and knowledge_type in q["types"]
            and q["priority"] <= guidance["max_priority"]
            and q["category"] in preferred
            and (q["only_after"] is None or q["only_after"] in yes_answers)
        ),
        key=_sort_key,
    )

    chosen, total = [], 0

    def add(question):
        nonlocal total
        if question in chosen or total + question["time"] > max_time:
            return False
        chosen.append(question)
        total += question["time"]
        return True

    # Pass 1: yes/no questions the master already answered "yes", with their follow-ups
    for question in pool:
        if question["id"] in yes_answers:
            add(question)
    for question in pool:
        if question["only_after"] in yes_answers:
            add(question)

    # Pass 2: one question per category, in teaching order.
    # Inside a category the most important and then the shortest one wins,
    # so even a 3-minute video covers goal, demonstration, mistake and check.
    for category in CATEGORY_ORDER:
        if any(q["category"] == category for q in chosen):
            continue
        candidates = sorted(
            (q for q in pool if q["category"] == category and q["only_after"] is None),
            key=lambda q: (q["priority"], q["time"], q["id"]),
        )
        for question in candidates:
            if add(question):
                break

    # Pass 3: fill the remaining time, most important first
    for question in pool:
        if question["only_after"] is None:
            add(question)

    # Teaching order; inside a category the yes/no question stays before its follow-ups
    chosen.sort(key=lambda q: (CATEGORY_ORDER.index(q["category"]), q["only_after"] is not None, q["priority"], q["id"]))
    return chosen


def recommended_questions(level):
    """Questions shown next to the lesson list in the course studio, grouped by category.

    [{"category": "goal", "category_label": "Learning goal", "questions": [<question dict>, ...]}, ...]

    Only questions a master answers with a video/text (answer_type == "media") are used.
    The "video_quality" category (filming tips) is skipped. level=None means all levels.
    """
    groups = []
    for category in CATEGORY_ORDER:
        if category == "video_quality":
            continue
        questions = sorted(
            (
                q for q in QUESTIONS
                if q["category"] == category
                and q["answer_type"] == "media"
                and (level is None or level in q["levels"])
            ),
            key=_sort_key,
        )
        if questions:
            groups.append({
                "category": category,
                "category_label": category_label(category),
                "questions": questions,
            })
    return groups


def total_time(questions):
    """Total answer time of the selected questions, in seconds."""
    return sum(q["time"] for q in questions)