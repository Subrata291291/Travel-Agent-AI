"""create initial application schema

Revision ID: 0a91f6d42b70
Revises: None
"""

from alembic import op
import sqlalchemy as sa


revision = "0a91f6d42b70"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "bookings",
        sa.Column("booking_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("option_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("origin", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("departure_time", sa.String(64), nullable=False),
        sa.Column("arrival_time", sa.String(64), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("travellers", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_session_id", "bookings", ["session_id"])
    op.create_index("ix_bookings_option_id", "bookings", ["option_id"])
    op.create_index("ix_bookings_idempotency_key", "bookings", ["idempotency_key"], unique=True)

    op.create_table(
        "hotel_bookings",
        sa.Column("booking_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("hotel_id", sa.String(64), nullable=False),
        sa.Column("hotel_name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("check_in_date", sa.String(32), nullable=False),
        sa.Column("check_out_date", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("price_per_night", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("travellers", sa.Integer(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hotel_bookings_user_id", "hotel_bookings", ["user_id"])
    op.create_index("ix_hotel_bookings_session_id", "hotel_bookings", ["session_id"])
    op.create_index("ix_hotel_bookings_hotel_id", "hotel_bookings", ["hotel_id"])
    op.create_index("ix_hotel_bookings_idempotency_key", "hotel_bookings", ["idempotency_key"], unique=True)

    op.create_table(
        "workflow_states",
        sa.Column("session_id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_states_user_id", "workflow_states", ["user_id"])


def downgrade() -> None:
    op.drop_table("workflow_states")
    op.drop_table("hotel_bookings")
    op.drop_table("bookings")
    op.drop_table("users")
    op.drop_table("tenants")
