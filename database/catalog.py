"""Read-only catalog queries. They return public card data, never lesson content.

Published private courses remain discoverable. Opening their lessons still requires
an enrollment/approval; that authorization belongs to backend/access.py.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from backend.i18n import _
from core.questions import LEVELS
from database import db
from database.models import Company, Course, Lesson

COURSE_SEARCH_COLUMNS = {
    "topic": (Course.title, Course.topic, Course.description),
    "profession": (Course.profession,),
    "result": (Course.outcome,),
}
COMPANY_SEARCH_COLUMNS = {
    "topic": Course.topic,
    "company": Company.name,
    "profession": Course.profession,
    "result": Course.outcome,
}


def published_topics():
    """Sorted, nonempty topics for the existing exact-match filter."""
    rows = (
        db.session.query(Course.topic)
        .filter(
            Course.status == "published", Course.topic.isnot(None), Course.topic != ""
        )
        .distinct()
        .order_by(Course.topic)
        .all()
    )
    return [topic for (topic,) in rows]


def search_companies(q, by):
    """Companies with matching published courses; count matching courses only.

    Private courses count too. Unknown modes return an empty list for API
    compatibility. Grouping in SQL avoids loading all matching course objects.
    """
    column = COMPANY_SEARCH_COLUMNS.get(by)
    if column is None:
        return []

    query = (
        db.session.query(Company, func.count(Course.id))
        .join(Course, Course.company_id == Company.id)
        .filter(Course.status == "published")
    )
    text = (q or "").strip()
    if text:
        query = query.filter(column.ilike(f"%{text}%"))

    # Order by the first matching course, as in the former course-by-course query.
    rows = query.group_by(Company.id).order_by(func.min(Course.id)).all()
    return [
        {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "course_count": count,
            "avatar_url": company.avatar_url,
            "url": f"/company/{company.id}",
        }
        for company, count in rows
    ]


def search_courses(q, by, language=None, topic=None, limit=None):
    """Published course cards, newest first, including approval-based courses.

    `topic` is an exact existing Topic value, not an additional tag system.
    `limit` is applied in SQL (the homepage requests three cards).
    Each card uses an aggregate lesson count instead of loading lesson bodies.
    """
    columns = COURSE_SEARCH_COLUMNS.get(by)
    if columns is None:
        return []

    lesson_counts = (
        db.session.query(Lesson.course_id, func.count(Lesson.id).label("total"))
        .group_by(Lesson.course_id)
        .subquery()
    )
    query = (
        db.session.query(Course, func.coalesce(lesson_counts.c.total, 0))
        .outerjoin(lesson_counts, lesson_counts.c.course_id == Course.id)
        .options(joinedload(Course.company))
        .filter(Course.status == "published")
    )
    text = (q or "").strip()
    if text:
        query = query.filter(or_(*(column.ilike(f"%{text}%") for column in columns)))
    if language:
        query = query.filter(Course.language == language)
    if topic:
        query = query.filter(Course.topic == topic)

    query = query.order_by(Course.created_at.desc())
    if limit is not None:
        query = query.limit(limit)

    return [_course_card(course, lesson_count) for course, lesson_count in query.all()]


def _course_card(course, lesson_count):
    """One stable response shape, shared by HTML and JSON catalog rendering."""
    return {
        "type": "course",
        "id": course.id,
        "title": course.title,
        "topic": course.topic,
        "description": course.description,
        "level": _(LEVELS.get(course.level, course.level)),
        "lesson_count": lesson_count,
        "language": course.language,
        "is_private": course.is_private,
        "url": f"/course/{course.id}",
        "company_id": course.company_id,
        "company_name": course.company.display_name,
        "company_url": f"/company/{course.company_id}",
    }
