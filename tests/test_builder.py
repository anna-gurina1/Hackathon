import pytest

from core.course_builder import category_label, recommended_questions, select_questions, total_time
from core.questions import CATEGORIES, DURATIONS, LEVELS, QUESTIONS, TYPES

ALL_COMBINATIONS = [
    (level, kind, duration)
    for level in LEVELS
    for kind in TYPES
    for duration in DURATIONS
]


@pytest.mark.parametrize("level, kind, duration", ALL_COMBINATIONS)
def test_fits_into_duration_and_not_empty(level, kind, duration):
    questions = select_questions(level, kind, duration)
    assert questions, "every combination must give the master something to answer"
    assert total_time(questions) <= duration * 60


@pytest.mark.parametrize("level, kind, duration", ALL_COMBINATIONS)
def test_questions_match_level_and_type(level, kind, duration):
    for q in select_questions(level, kind, duration):
        assert level in q["levels"]
        assert kind in q["types"]


@pytest.mark.parametrize("level, kind, duration", ALL_COMBINATIONS)
def test_teaching_order(level, kind, duration):
    order = list(CATEGORIES)
    positions = [order.index(q["category"]) for q in select_questions(level, kind, duration)]
    assert positions == sorted(positions)


def test_short_course_starts_with_goal():
    questions = select_questions("beginner", "procedure", 3)
    assert questions[0]["category"] == "goal"
    assert total_time(questions) <= 180


def test_longer_course_has_more_questions():
    short = select_questions("intermediate", "practical_skill", 3)
    long = select_questions("intermediate", "practical_skill", 15)
    assert len(long) > len(short)


def test_no_duplicates():
    questions = select_questions("advanced", "decision_making", 15)
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids))


def test_follow_ups_only_after_yes():
    follow_ups = {q["id"] for q in QUESTIONS if q["only_after"] is not None}
    parent_ids = {q["only_after"] for q in QUESTIONS if q["only_after"] is not None}

    without_yes = select_questions("intermediate", "procedure", 15)
    assert not follow_ups & {q["id"] for q in without_yes}

    with_yes = select_questions("intermediate", "procedure", 15, yes_answers=parent_ids)
    assert follow_ups & {q["id"] for q in with_yes}


def test_unknown_duration_uses_closest():
    assert select_questions("beginner", "procedure", 4) == select_questions("beginner", "procedure", 5)


def test_category_label():
    assert category_label("mistake") == CATEGORIES["mistake"]
    assert category_label("unknown") == "unknown"


@pytest.mark.parametrize("level", list(LEVELS) + [None])
def test_recommended_questions(level):
    groups = recommended_questions(level)
    assert groups
    order = list(CATEGORIES)
    positions = [order.index(g["category"]) for g in groups]
    assert positions == sorted(positions)  # same order as CATEGORIES
    for group in groups:
        assert group["category"] != "video_quality"
        assert group["category_label"] == category_label(group["category"])
        assert group["questions"]
        for q in group["questions"]:
            assert q["answer_type"] == "media"
            assert q["category"] == group["category"]
            assert level is None or level in q["levels"]