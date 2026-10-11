"""add persistent user memories

Revision ID: 8a4c2e1f6b90
Revises: d3e9a6f8b21c
"""
from alembic import op
import sqlalchemy as sa

revision = "8a4c2e1f6b90"
down_revision = "d3e9a6f8b21c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column("memory_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("topic", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="semantic"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("source_quote", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_memories_user_id", "user_memories", ["user_id"])
    op.create_index("ix_user_memories_tenant_id", "user_memories", ["tenant_id"])
    op.create_index("ix_user_memories_owner_status", "user_memories", ["user_id", "tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_user_memories_owner_status", table_name="user_memories")
    op.drop_index("ix_user_memories_tenant_id", table_name="user_memories")
    op.drop_index("ix_user_memories_user_id", table_name="user_memories")
    op.drop_table("user_memories")
