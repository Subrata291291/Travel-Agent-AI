"""enforce case-insensitive unique user emails

Revision ID: 7bc11488f3c2
Revises: 1856c6a98854
"""

from alembic import op
import sqlalchemy as sa


revision = "7bc11488f3c2"
down_revision = "1856c6a98854"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            "SELECT 1 FROM users GROUP BY lower(email) "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates:
        raise RuntimeError(
            "Cannot enforce unique user emails: duplicate addresses exist "
            "(case-insensitive). Resolve duplicates without deleting user data, "
            "then rerun this migration."
        )

    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_lower", table_name="users")
