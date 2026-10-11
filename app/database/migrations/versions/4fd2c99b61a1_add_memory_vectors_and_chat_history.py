"""add user memory vectors and durable chat history

Revision ID: 4fd2c99b61a1
Revises: 8a4c2e1f6b90
"""
from alembic import op
import sqlalchemy as sa


revision = "4fd2c99b61a1"
down_revision = "8a4c2e1f6b90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_memory_embeddings",
        sa.Column("memory_id", sa.String(64), sa.ForeignKey("user_memories.memory_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_user_memory_embeddings_model_dimensions",
        "user_memory_embeddings", ["model", "dimensions"],
    )

    op.create_table(
        "conversation_messages",
        sa.Column("message_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("session_key", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_conversation_messages_scope_order",
        "conversation_messages", ["tenant_id", "user_id", "session_key", "message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_scope_order", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_user_memory_embeddings_model_dimensions", table_name="user_memory_embeddings")
    op.drop_table("user_memory_embeddings")
