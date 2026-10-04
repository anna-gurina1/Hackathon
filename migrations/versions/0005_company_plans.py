"""Tariffs of a company: company_profile.plan and company_profile.course_credits.

The old company_profile.is_pro column is replaced by the plan:
is_pro = true  ->  plan = "monthly",  otherwise plan = "free". Then the column is dropped
(models.py has CompanyProfile.is_pro as a property now).

Safe to run twice: every step is skipped if it was already done.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("company_profile")}

    with op.batch_alter_table("company_profile") as batch:
        if "plan" not in columns:
            batch.add_column(
                sa.Column("plan", sa.String(length=20), nullable=False, server_default="free")
            )
        if "course_credits" not in columns:
            batch.add_column(
                sa.Column("course_credits", sa.Integer(), nullable=False, server_default="0")
            )

    if "is_pro" in columns:
        company = sa.table("company_profile", sa.column("plan", sa.String), sa.column("is_pro", sa.Boolean))
        op.execute(company.update().where(company.c.is_pro == sa.true()).values(plan="monthly"))
        with op.batch_alter_table("company_profile") as batch:
            batch.drop_column("is_pro")


def downgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("company_profile")}
    with op.batch_alter_table("company_profile") as batch:
        if "is_pro" not in columns:
            batch.add_column(
                sa.Column("is_pro", sa.Boolean(), nullable=False, server_default=sa.false())
            )
    company = sa.table("company_profile", sa.column("plan", sa.String), sa.column("is_pro", sa.Boolean))
    op.execute(
        company.update().where(company.c.plan.in_(["per_course", "monthly"])).values(is_pro=True)
    )
    with op.batch_alter_table("company_profile") as batch:
        batch.drop_column("plan")
        batch.drop_column("course_credits")