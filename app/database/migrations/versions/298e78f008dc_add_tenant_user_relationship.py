"""add tenant user relationship

Revision ID: 298e78f008dc
Revises:
Create Date: 2026-10-07 17:25:49.817807

"""

from typing import Sequence, Union

from alembic import op


# ---------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------

revision: str = "298e78f008dc"

down_revision: Union[str, Sequence[str], None] = "0a91f6d42b70"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------
# Upgrade
# ---------------------------------------------------------

def upgrade() -> None:
    """
    Add the Tenant -> User foreign-key relationship.

    Existing booking/idempotency indexes are intentionally
    not modified by this migration.
    """

    with op.batch_alter_table(
        "users",
        schema=None,
    ) as batch_op:

        batch_op.create_foreign_key(
            "fk_users_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["tenant_id"],
        )


# ---------------------------------------------------------
# Downgrade
# ---------------------------------------------------------

def downgrade() -> None:
    """
    Remove the Tenant -> User foreign-key relationship.
    """

    with op.batch_alter_table(
        "users",
        schema=None,
    ) as batch_op:

        batch_op.drop_constraint(
            "fk_users_tenant_id_tenants",
            type_="foreignkey",
        )
