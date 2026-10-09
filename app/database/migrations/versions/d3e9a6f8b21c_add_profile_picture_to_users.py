"""add profile picture data to users

Revision ID: d3e9a6f8b21c
Revises: 7bc11488f3c2
"""

from alembic import op
import sqlalchemy as sa


revision = "d3e9a6f8b21c"
down_revision = "7bc11488f3c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_picture_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "profile_picture_data")
