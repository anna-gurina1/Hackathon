"""Site language of a user: user.language ("en", "ru" or empty = not chosen yet).

Safe to run twice: the column is added only if it is missing.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}
    if "language" not in columns:
        with op.batch_alter_table("user") as batch:
            batch.add_column(sa.Column("language", sa.String(length=5), nullable=True))


def downgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}
    if "language" in columns:
        with op.batch_alter_table("user") as batch:
            batch.drop_column("language")
