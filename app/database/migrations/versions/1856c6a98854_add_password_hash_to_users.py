"""add password hash to users

Revision ID: 1856c6a98854
Revises: <YOUR_PREVIOUS_REVISION>
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1856c6a98854"

# IMPORTANT:
# Keep the value that Alembic generated in your file.
# Do NOT invent a revision ID here.
down_revision = "c5dfc0f04eb3"

branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add password_hash to users.

    Nullable is intentional because existing users do not
    have passwords yet.
    """

    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """
    Remove password_hash if this migration is rolled back.
    """

    op.drop_column(
        "users",
        "password_hash",
    )