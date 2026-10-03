"""Profile photo / company logo (user.avatar).

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}
    if "avatar" not in columns:
        with op.batch_alter_table("user") as batch:
            batch.add_column(sa.Column("avatar", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("user") as batch:
        batch.drop_column("avatar")
