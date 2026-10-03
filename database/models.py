import os
import secrets
from datetime import datetime

from flask_login import UserMixin

from database import db


# ---------------------------------------------------------------------------
# Users (existing — kept as is)
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    """Account. type='person' or 'company' decides which profile is attached."""
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # "person" | "company"
    email = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Magic-login token. Rotated on every successful login so a used link
    # cannot be replayed.
    login_nonce = db.Column(db.String(32), default=lambda: secrets.token_hex(16), nullable=False)

    person = db.relationship(
        "PersonProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    company = db.relationship(
        "CompanyProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def rotate_login_nonce(self):
        """Invalidate the current login link (called after each successful login)."""
        self.login_nonce = secrets.token_hex(16)

    @property
    def is_person(self):
        return self.type == "person"

    @property
    def is_company(self):
        return self.type == "company"

    @property
    def display_name(self):
        if self.is_company and self.company:
            return self.company.name
        if self.person:
            return f"{self.person.first_name} {self.person.last_name}"
        return self.email

    @property
    def initials(self):
        if self.is_company and self.company:
            return self.company.name[:1].upper()
        if self.person:
            return (self.person.first_name[:1] + self.person.last_name[:1]).upper()
        return self.email[:1].upper()


class PersonProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)


class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    topic = db.Column(db.String(100), nullable=True)
    profession = db.Column(db.String(100), nullable=True)
    outcome = db.Column(db.Text, nullable=True)  # what the learner will be able to do

    level = db.Column(db.String(20), nullable=False)          # key from LEVELS
    knowledge_type = db.Column(db.String(30), nullable=False)  # key from TYPES
    duration = db.Column(db.Integer, nullable=False)          # minutes, one of DURATIONS

    is_private = db.Column(db.Boolean, default=False, nullable=False)
    invite_token = db.Column(
        db.String(64), unique=True, default=lambda: secrets.token_urlsafe(16), nullable=False
    )
    status = db.Column(db.String(20), default="draft", nullable=False)  # "draft" | "published"

    # Comma-separated ids of yes_no questions the master answered "yes" to.
    yes_answers = db.Column(db.String(300), default="", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship("User")
    lessons = db.relationship(
        "Lesson", backref="course", order_by="Lesson.order", cascade="all, delete-orphan"
    )
    enrollments = db.relationship("Enrollment", backref="course", cascade="all, delete-orphan")
    offers = db.relationship("Offer", backref="course", cascade="all, delete-orphan")

    @property
    def lesson_count(self):
        return len(self.lessons)

    @property
    def yes_answer_ids(self):
        return {int(x) for x in self.yes_answers.split(",") if x}


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)

    order = db.Column(db.Integer, nullable=False)  # 1, 2, 3, ...
    title = db.Column(db.String(200), nullable=False)
    question_id = db.Column(db.Integer, nullable=True)  # id from core.questions.QUESTIONS

    video_filename = db.Column(db.String(255), nullable=True)  # name of file in uploads/
    text = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz = db.relationship(
        "Quiz", backref="lesson", uselist=False, cascade="all, delete-orphan"
    )

    def delete_video_file(self, upload_folder):
        """Remove this lesson's video from disk (if any) and clear the field.
        Caller (backend) is responsible for db.session.commit() afterwards."""
        if self.video_filename:
            path = os.path.join(upload_folder, self.video_filename)
            if os.path.exists(path):
                os.remove(path)
            self.video_filename = None


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), unique=True, nullable=False)
    pass_score = db.Column(db.Integer, default=70, nullable=False)  # percent

    questions = db.relationship(
        "QuizQuestion", backref="quiz", order_by="QuizQuestion.id", cascade="all, delete-orphan"
    )
    attempts = db.relationship(
        "QuizAttempt", backref="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=True)  # key from CATEGORIES, source template

    answers = db.relationship(
        "QuizAnswer", backref="question", order_by="QuizAnswer.id", cascade="all, delete-orphan"
    )


class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("quiz_question.id"), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)

    status = db.Column(db.String(20), default="in_progress", nullable=False)  # in_progress | completed
    current_lesson = db.Column(db.Integer, default=1, nullable=False)  # order number, unlocked up to

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_enrollment_user_course"),
    )

    @property
    def progress_percent(self):
        if self.status == "completed":
            return 100
        total = self.course.lesson_count if self.course else 0
        if total == 0:
            return 0
        completed_lessons = max(self.current_lesson - 1, 0)
        return min(round(completed_lessons / total * 100), 100)


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)   # percent
    passed = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class Offer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)

    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship("User", foreign_keys=[company_id])
    user = db.relationship("User", foreign_keys=[user_id])