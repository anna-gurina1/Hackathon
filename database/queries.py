"""
Dashboard queries and course visibility.

Catalog SQL lives in database/catalog.py; search helpers remain re-exported here
for compatibility. Routes must still authorize company dashboard access.
"""

from sqlalchemy.orm import joinedload, selectinload

# Compatibility imports: existing callers can still import these query helpers here.
from database.catalog import search_companies, search_courses
from database import db
from database.models import (
    AccessRequest,
    Course,
    Enrollment,
    Lesson,
    Offer,
    Quiz,
    QuizAttempt,
    User,
)

__all__ = [
    "search_companies",
    "search_courses",
    "course_visible_to",
    "person_dashboard",
    "company_dashboard",
    "best_score",
]


def course_visible_to(course, user):
    """True if `user` (possibly anonymous) is allowed to view `course`."""
    from backend.access import can_edit_course

    if can_edit_course(course, user):
        return True
    if course.status != "published":
        return False
    if not course.is_private:
        return True

    if not getattr(user, "is_authenticated", False):
        return False

    return (
        Enrollment.query.filter_by(user_id=user.id, course_id=course.id).first()
        is not None
    )


def person_dashboard(user):
    """Enrollments, started/completed counts and received offers for a person."""
    enrollments = (
        Enrollment.query.filter_by(user_id=user.id)
        .order_by(Enrollment.started_at.desc())
        .all()
    )
    completed = sum(1 for e in enrollments if e.status == "completed")

    offers = (
        Offer.query.filter_by(user_id=user.id).order_by(Offer.created_at.desc()).all()
    )

    # Requests to private courses that are not accepted yet (waiting or declined)
    requests = (
        AccessRequest.query.filter(
            AccessRequest.user_id == user.id, AccessRequest.status != "accepted"
        )
        .order_by(AccessRequest.created_at.desc())
        .all()
    )

    return {
        "enrollments": enrollments,
        "stats": {"started": len(enrollments), "completed": completed},
        "offers": offers,
        "requests": requests,
    }


def company_dashboard(company):
    """Owner-only dashboard data; the route checks authorization before calling.

    Batch related records and score/offer lookups instead of querying once per
    course, completer and candidate. The response keys and score meaning stay
    compatible with the existing templates.
    """
    company_id = company.id
    courses = (
        Course.query.filter_by(company_id=company_id)
        .options(
            # Dashboard templates count lessons; their text/video fields are not needed.
            selectinload(Course.lessons).load_only(Lesson.id, Lesson.course_id),
            selectinload(Course.enrollments)
            .joinedload(Enrollment.user)
            .joinedload(User.person),
        )
        .order_by(Course.created_at.desc())
        .all()
    )
    course_ids = [course.id for course in courses]
    if not course_ids:
        return {"courses": [], "candidates": [], "requests": []}

    scores = _course_scores(course_ids)
    sent_offers = {
        (user_id, course_id)
        for user_id, course_id in db.session.query(Offer.user_id, Offer.course_id)
        .filter(Offer.company_id == company_id, Offer.course_id.in_(course_ids))
        .all()
    }
    completed_enrollments = (
        Enrollment.query.filter(
            Enrollment.course_id.in_(course_ids), Enrollment.status == "completed"
        )
        .options(
            joinedload(Enrollment.user).joinedload(User.person),
            joinedload(Enrollment.course),
        )
        .order_by(Enrollment.completed_at.desc())
        .all()
    )
    candidates = [
        {
            "user": enrollment.user,
            "course": enrollment.course,
            "score": scores.get((enrollment.user_id, enrollment.course_id)),
            "completed_at": enrollment.completed_at,
            "offer_sent": (enrollment.user_id, enrollment.course_id) in sent_offers,
        }
        for enrollment in completed_enrollments
    ]
    requests = (
        AccessRequest.query.filter(
            AccessRequest.course_id.in_(course_ids), AccessRequest.status == "pending"
        )
        .options(joinedload(AccessRequest.user).joinedload(User.person))
        .order_by(AccessRequest.created_at)
        .all()
    )
    return {
        "courses": [_company_course_row(course, scores) for course in courses],
        "candidates": candidates,
        "requests": requests,
    }


def _company_course_row(course, scores):
    """Counts, invitation link and completers for one owned course."""
    completed = [e for e in course.enrollments if e.status == "completed"]
    newest_first = sorted(
        completed, key=lambda e: e.completed_at or e.started_at, reverse=True
    )
    return {
        "course": course,
        "enrolled": len(course.enrollments),
        "completed": len(completed),
        "invite_url": (
            f"/course/private/{course.invite_token}"
            if course.is_private and course.status == "published"
            else None
        ),
        "completers": [
            {
                "user": enrollment.user,
                "email": enrollment.user.email,
                "score": scores.get((enrollment.user_id, course.id)),
                "completed_at": enrollment.completed_at,
            }
            for enrollment in newest_first
        ],
    }


def _course_scores(course_ids):
    """(learner ID, course ID) -> highest quiz attempt, including failed attempts.

    This is deliberately the same meaning as best_score(), not an average,
    final exam mark or a new ranking of candidates.
    """
    rows = (
        db.session.query(
            QuizAttempt.user_id, Lesson.course_id, db.func.max(QuizAttempt.score)
        )
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .join(Lesson, Quiz.lesson_id == Lesson.id)
        .filter(Lesson.course_id.in_(course_ids))
        .group_by(QuizAttempt.user_id, Lesson.course_id)
        .all()
    )
    return {(user_id, course_id): score for user_id, course_id, score in rows}


def best_score(user_id, course_id):
    """Highest QuizAttempt.score this user has on any quiz of this course, or None."""
    return (
        db.session.query(db.func.max(QuizAttempt.score))
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .join(Lesson, Quiz.lesson_id == Lesson.id)
        .filter(Lesson.course_id == course_id, QuizAttempt.user_id == user_id)
        .scalar()
    )
