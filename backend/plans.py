"""Tariff limits of a company (demo payment: the pricing page button just switches the plan).

    plan          courses                       videos per course   private courses
    "free"        1                             3                   no
    "per_course"  1 + bought courses            10                  yes
    "monthly"     unlimited                     unlimited           yes

All courses count, drafts too. A deleted course frees its place.
There is no limit on the length of a video on any plan.
The limits are checked here on the server: the page only hides buttons, and that can be bypassed.
"""
from database.models import Course

PLAN_LABELS = {"free": "Free", "per_course": "Per course", "monthly": "Monthly"}
VIDEO_LIMITS = {"free": 3, "per_course": 10, "monthly": None}  # None = unlimited


def plan_of(company_user):
    """Plan key of a company account. Unknown or missing -> "free"."""
    company = company_user.company if company_user is not None else None
    plan = company.plan if company is not None else None
    return plan if plan in PLAN_LABELS else "free"


def course_limit(company_user):
    """How many courses the company may have. None = unlimited."""
    plan = plan_of(company_user)
    if plan == "monthly":
        return None
    if plan == "per_course":
        return 1 + max(0, company_user.company.course_credits or 0)
    return 1


def courses_used(company_user):
    """How many courses the company has now (drafts included)."""
    return Course.query.filter_by(company_id=company_user.id).count()


def can_create_course(company_user):
    limit = course_limit(company_user)
    return limit is None or courses_used(company_user) < limit


def video_limit(company_user):
    """How many videos one course of this company may have. None = unlimited."""
    return VIDEO_LIMITS[plan_of(company_user)]


def videos_used(course):
    """How many lessons of the course have a video."""
    return sum(1 for lesson in course.lessons if lesson.video_filename)


def can_add_video(course):
    limit = video_limit(course.company)
    return limit is None or videos_used(course) < limit