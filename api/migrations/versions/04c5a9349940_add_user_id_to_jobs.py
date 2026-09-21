"""add user_id to jobs

Revision ID: 04c5a9349940
Revises: 95f7243488e4
Create Date: 2026-09-21 12:36:14.914104

Jobs ingested before authentication existed have no owner and cannot be
attributed to one, so this migration deletes them rather than inventing a
user to hang them on. They were walking-skeleton test rows; nothing else has
ever been stored.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "04c5a9349940"
down_revision: str | Sequence[str] | None = "95f7243488e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = "fk_jobs_user_id_users"


def upgrade() -> None:
    # Added nullable first: an existing table cannot take a NOT NULL column
    # without a value for every row.
    op.add_column("jobs", sa.Column("user_id", sa.UUID(), nullable=True))

    # Pre-auth rows have no owner. See the module docstring.
    op.execute("DELETE FROM jobs WHERE user_id IS NULL")

    op.alter_column("jobs", "user_id", nullable=False)
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)
    op.create_unique_constraint("uq_jobs_user_content", "jobs", ["user_id", "content_hash"])
    op.create_foreign_key(
        FK_NAME, "jobs", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "jobs", type_="foreignkey")
    op.drop_constraint("uq_jobs_user_content", "jobs", type_="unique")
    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")
    op.drop_column("jobs", "user_id")
