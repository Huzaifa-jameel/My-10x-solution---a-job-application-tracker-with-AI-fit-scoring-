"""allow cache as a scored_by value

Revision ID: fedf7af631a1
Revises: 90644ad9d800
Create Date: 2026-09-21

Written by hand, for two reasons.

Alembic's autogenerate does not compare CHECK constraints. That is also why
ck_jobs_scored_by was never created in the first place: the migration that
added the scored_by column used add_column, which carried the column across
but silently dropped its constraint, leaving the model declaring a rule the
database was not enforcing. DROP ... IF EXISTS covers both states.

"""

from collections.abc import Sequence

from alembic import op

revision: str = "fedf7af631a1"
down_revision: str | Sequence[str] | None = "90644ad9d800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_jobs_scored_by"


def upgrade() -> None:
    op.execute(f"ALTER TABLE jobs DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.create_check_constraint(
        CONSTRAINT,
        "jobs",
        "scored_by IS NULL OR scored_by IN ('groq', 'fallback', 'cache')",
    )


def downgrade() -> None:
    # Rows scored from cache would violate the narrower constraint, so they are
    # relabelled rather than blocking the downgrade.
    op.execute("UPDATE jobs SET scored_by = 'groq' WHERE scored_by = 'cache'")
    op.execute(f"ALTER TABLE jobs DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.create_check_constraint(
        CONSTRAINT,
        "jobs",
        "scored_by IS NULL OR scored_by IN ('groq', 'fallback')",
    )
