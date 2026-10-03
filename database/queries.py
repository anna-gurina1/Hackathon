"""
Ready-made query functions for backend routes.
Backend calls these instead of writing its own queries — keep the
function names and signatures exactly as listed here.
"""

from database import db
from database.models import (
    CompanyProfile,
    Course,
    Enrollment,
    Lesson,
    Offer,
    Quiz,
    QuizAttempt,
    User,
)

_SEARCH_COLUMNS = {
    "topic": lambda: Course.topic,
    "company": lambda: CompanyProfile.name,
    "profession": lambda: Course.profession,
    "result": lambda: Course.outcome,
}


def course_visible_to(course, user):
    """True if `user` (possibly anonymous) is allowed to view `course`."""
    if not course.is_private and course.status == "published":
        return True

    if not getattr(user, "is_authenticated", False):
        return False

    if course.company_id == user.id:
        return True

    return (
        Enrollment.query.filter_by(user_id=user.id, course_id=course.id).first()
        is not None
    )


def search_companies(q, by):
    """
    Companies that have at least one public+published course matching the
    filter. `by` selects which column is matched with ILIKE against `q`:
    "topic" -> Course.topic, "company" -> CompanyProfile.name,
    "profession" -> Course.profession, "result" -> Course.outcome.
    An empty `q` returns companies with any public+published course.
    """
    column_factory = _SEARCH_COLUMNS.get(by)
    if column_factory is None:
        return []

    query = (
        db.session.query(Course)
        .join(User, Course.company_id == User.id)
        .join(CompanyProfile, CompanyProfile.user_id == User.id)
        .filter(Course.is_private.is_(False), Course.status == "published")
    )

    q = (q or "").strip()
    if q:
        query = query.filter(column_factory().ilike(f"%{q}%"))

    companies = {}
    for course in query.all():
        company_id = course.company_id
        if company_id not in companies:
            profile = course.company.company
            companies[company_id] = {
                "id": company_id,
                "name": profile.name if profile else "",
                "description": profile.description if profile else None,
                "course_count": 0,
                "url": f"/company/{company_id}",
            }
        companies[company_id]["course_count"] += 1

    return list(companies.values())


def person_dashboard(user):
    """Enrollments, started/completed counts and received offers for a person."""
    enrollments = (
        Enrollment.query.filter_by(user_id=user.id)
        .order_by(Enrollment.started_at.desc())
        .all()
    )
    completed = sum(1 for e in enrollments if e.status == "completed")

    offers = (
        Offer.query.filter_by(user_id=user.id)
        .order_by(Offer.created_at.desc())
        .all()
    )

    return {
        "enrollments": enrollments,
        "stats": {"started": len(enrollments), "completed": completed},
        "offers": offers,
    }


def company_dashboard(user):
    """This company's courses (with enrollment counts) and its candidates."""
    courses = (
        Course.query.filter_by(company_id=user.id)
        .order_by(Course.created_at.desc())
        .all()
    )

    course_rows = []
    for course in courses:
        enrolled = len(course.enrollments)
        completed = sum(1 for e in course.enrollments if e.status == "completed")
        invite_url = f"/course/private/{course.invite_token}" if course.is_private else None
        # People who finished this course, newest first: their emails are shown on the course card
        completers = [
            {
                "user": e.user,
                "email": e.user.email,
                "score": best_score(e.user_id, course.id),
                "completed_at": e.completed_at,
            }
            for e in sorted(
                (e for e in course.enrollments if e.status == "completed"),
                key=lambda e: e.completed_at or e.started_at,
                reverse=True,
            )
        ]
        course_rows.append({
            "course": course,
            "enrolled": enrolled,
            "completed": completed,
            "invite_url": invite_url,
            "completers": completers,
        })

    candidates = []
    course_ids = [c.id for c in courses]
    if course_ids:
        completed_enrollments = (
            Enrollment.query.filter(
                Enrollment.course_id.in_(course_ids),
                Enrollment.status == "completed",
            )
            .order_by(Enrollment.completed_at.desc())
            .all()
        )
        for enrollment in completed_enrollments:
            offer_sent = (
                Offer.query.filter_by(
                    company_id=user.id,
                    user_id=enrollment.user_id,
                    course_id=enrollment.course_id,
                ).first()
                is not None
            )
            candidates.append({
                "user": enrollment.user,
                "course": enrollment.course,
                "score": best_score(enrollment.user_id, enrollment.course_id),
                "completed_at": enrollment.completed_at,
                "offer_sent": offer_sent,
            })

    return {"courses": course_rows, "candidates": candidates}


def best_score(user_id, course_id):
    """Highest QuizAttempt.score this user has on any quiz of this course, or None."""
    return (
        db.session.query(db.func.max(QuizAttempt.score))
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .join(Lesson, Quiz.lesson_id == Lesson.id)
        .filter(Lesson.course_id == course_id, QuizAttempt.user_id == user_id)
        .scalar()
    )