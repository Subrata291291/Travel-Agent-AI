import pytest
from fastapi import HTTPException

from app.auth.dependencies import require_roles
from app.core.tenant_context import TenantContext


def test_admin_role_allows_admin():
    """
    The admin authorization dependency should allow
    a user whose current database role is admin.
    """

    context = TenantContext(
        user_id="admin_user",
        tenant_id="test_tenant",
        role="admin",
    )

    admin_checker = require_roles("admin")

    result = admin_checker(context)

    assert result == context
    assert result.user_id == "admin_user"
    assert result.tenant_id == "test_tenant"
    assert result.role == "admin"


def test_admin_role_rejects_normal_user():
    """
    The admin authorization dependency should reject
    a normal user.
    """

    context = TenantContext(
        user_id="normal_user",
        tenant_id="test_tenant",
        role="user",
    )

    admin_checker = require_roles("admin")

    with pytest.raises(HTTPException) as exc_info:
        admin_checker(context)

    assert exc_info.value.status_code == 403
    assert (
        exc_info.value.detail
        == "You do not have permission to access this resource."
    )