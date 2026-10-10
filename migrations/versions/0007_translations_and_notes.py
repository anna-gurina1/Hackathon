"""Three small additions:

- course.language: "en" / "ru", the language the course is written in (chip in the catalog);
  filled for the existing courses here.
- answered_question: the master's own notes "I have answered this question" in the studio.
  Questions that old lessons were made from (the old "Use" button) become such notes.
- translation: saved AI translations of user texts (the "Translate" button).

Safe to run twice: nothing is created if it already exists.

Revision ID: 0007
Revises: 0006
"""
import re

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _text_language(text):
    """Same rule as backend/translator.py: more Russian letters -> "ru", more Latin -> "en"."""
    latin = len(re.findall(r"[A-Za-z]", text))
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    if latin == 0 and cyrillic == 0:
        return None
    return "ru" if cyrillic > latin else "en"


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "language" not in {c["name"] for c in inspector.get_columns("course")}:
        with op.batch_alter_table("course") as batch:
            batch.add_column(sa.Column("language", sa.String(length=5), nullable=True))
        courses = connection.execute(sa.text(
            "SELECT id, title, description, topic, profession, outcome FROM course"
        )).fetchall()
        for course_id, *texts in courses:
            language = _text_language(" ".join(text for text in texts if text))
            connection.execute(
                sa.text("UPDATE course SET language = :language WHERE id = :id"),
                {"language": language, "id": course_id},
            )

    if "answered_question" not in tables:
        op.create_table(
            "answered_question",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("course.id"), nullable=False),
            sa.Column("question_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("course_id", "question_id", name="uq_answered_question_course_question"),
        )
        connection.execute(sa.text(
            "INSERT INTO answered_question (course_id, question_id, created_at) "
            "SELECT DISTINCT course_id, question_id, CURRENT_TIMESTAMP FROM lesson WHERE question_id IS NOT NULL"
        ))

    if "translation" not in tables:
        op.create_table(
            "translation",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_hash", sa.String(length=64), nullable=False),
            sa.Column("language", sa.String(length=5), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("source_hash", "language", name="uq_translation_source_language"),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "translation" in tables:
        op.drop_table("translation")
    if "answered_question" in tables:
        op.drop_table("answered_question")
    if "language" in {c["name"] for c in inspector.get_columns("course")}:
        with op.batch_alter_table("course") as batch:
            batch.drop_column("language")
