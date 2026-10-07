"""add tenant ownership to business tables

Revision ID: c5dfc0f04eb3
Revises: 298e78f008dc
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5dfc0f04eb3"
down_revision: Union[str, Sequence[str], None] = "298e78f008dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add tenant ownership to business tables.

    Important:
    - Existing booking data must be preserved.
    - tenant_id is temporarily nullable during the migration.
    - Existing rows will be backfilled before the column becomes required.
    """

    # ---------------------------------------------------------
    # 1. Add tenant_id columns as nullable.
    # ---------------------------------------------------------
    #
    # We intentionally do NOT make them NOT NULL yet.
    #
    # Existing rows already exist in these tables, so SQLite
    # cannot safely add a required column without a value.
    #

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "tenant_id",
                sa.String(length=64),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_bookings_tenant_id",
            ["tenant_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_bookings_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["tenant_id"],
        )

    with op.batch_alter_table("hotel_bookings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "tenant_id",
                sa.String(length=64),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_hotel_bookings_tenant_id",
            ["tenant_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_hotel_bookings_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["tenant_id"],
        )

    with op.batch_alter_table("workflow_states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "tenant_id",
                sa.String(length=64),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_workflow_states_tenant_id",
            ["tenant_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_workflow_states_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["tenant_id"],
        )


def downgrade() -> None:
    """
    Remove tenant ownership from business tables.
    """

    with op.batch_alter_table("workflow_states", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_workflow_states_tenant_id_tenants",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_workflow_states_tenant_id")
        batch_op.drop_column("tenant_id")

    with op.batch_alter_table("hotel_bookings", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_hotel_bookings_tenant_id_tenants",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_hotel_bookings_tenant_id")
        batch_op.drop_column("tenant_id")

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_bookings_tenant_id_tenants",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_bookings_tenant_id")
        batch_op.drop_column("tenant_id")