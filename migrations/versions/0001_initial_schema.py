"""Initial schema (everything that existed before Flask-Migrate).

It works on an empty database AND on an old app.db made by db.create_all():
tables that already exist are skipped, and the two changes that migrate_db.py
used to make (company_profile.is_pro, optional course.knowledge_type / duration)
are applied only when they are missing. This replaces migrate_db.py.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("user"):
        op.create_table(
            "user",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("login_nonce", sa.String(length=32), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
        )

    if not inspector.has_table("company_profile"):
        op.create_table(
            "company_profile",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_pro", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("course"):
        op.create_table(
            "course",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("topic", sa.String(length=100), nullable=True),
            sa.Column("profession", sa.String(length=100), nullable=True),
            sa.Column("outcome", sa.Text(), nullable=True),
            sa.Column("level", sa.String(length=20), nullable=False),
            sa.Column("knowledge_type", sa.String(length=30), nullable=True),
            sa.Column("duration", sa.Integer(), nullable=True),
            sa.Column("is_private", sa.Boolean(), nullable=False),
            sa.Column("invite_token", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("yes_answers", sa.String(length=300), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('invite_token'),
        )

    if not inspector.has_table("person_profile"):
        op.create_table(
            "person_profile",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("first_name", sa.String(length=60), nullable=False),
            sa.Column("last_name", sa.String(length=60), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("enrollment"):
        op.create_table(
            "enrollment",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("current_lesson", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['course_id'], ['course.id']),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'course_id', name='uq_enrollment_user_course'),
        )

    if not inspector.has_table("lesson"):
        op.create_table(
            "lesson",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("question_id", sa.Integer(), nullable=True),
            sa.Column("video_filename", sa.String(length=255), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['course_id'], ['course.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("offer"):
        op.create_table(
            "offer",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['user.id']),
            sa.ForeignKeyConstraint(['course_id'], ['course.id']),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("quiz"):
        op.create_table(
            "quiz",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lesson_id", sa.Integer(), nullable=False),
            sa.Column("pass_score", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['lesson_id'], ['lesson.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('lesson_id'),
        )

    if not inspector.has_table("quiz_attempt"):
        op.create_table(
            "quiz_attempt",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("quiz_id", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("passed", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['quiz_id'], ['quiz.id']),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("quiz_question"):
        op.create_table(
            "quiz_question",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("quiz_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=30), nullable=True),
            sa.ForeignKeyConstraint(['quiz_id'], ['quiz.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table("quiz_answer"):
        op.create_table(
            "quiz_answer",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("question_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.String(length=300), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['question_id'], ['quiz_question.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    # --- old databases: bring existing tables up to date -------------------
    company_columns = {c["name"] for c in inspector.get_columns("company_profile")}
    if "is_pro" not in company_columns:
        op.add_column(
            "company_profile",
            sa.Column("is_pro", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    course_columns = {c["name"]: c for c in inspector.get_columns("course")}
    if not course_columns["knowledge_type"]["nullable"] or not course_columns["duration"]["nullable"]:
        with op.batch_alter_table("course") as batch_op:
            batch_op.alter_column(
                "knowledge_type", existing_type=sa.String(length=30), nullable=True
            )
            batch_op.alter_column("duration", existing_type=sa.Integer(), nullable=True)


def downgrade():
    # The first migration is the starting point: there is nothing older to go back to.
    pass
