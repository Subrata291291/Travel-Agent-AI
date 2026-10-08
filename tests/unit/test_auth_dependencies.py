import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import (
    get_current_context,
    has_required_role,
)
from app.auth.jwt import create_access_token


def credentials_for(
    user_id: str,
    tenant_id: str,
    role: str = "user",
) -> HTTPAuthorizationCredentials:
    """
    Create Bearer credentials containing a valid JWT.

    This helper keeps the individual tests small and readable.
    """

    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
    )

    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


def test_get_current_context_extracts_jwt_identity():
    """
    The JWT should provide the authenticated user's identity.

    get_current_context() intentionally does not trust the role
    from the JWT. The database is the source of truth for roles.
    """

    credentials = credentials_for(
        user_id="test_user",
        tenant_id="test_tenant",
        role="user",
    )

    context = get_current_context(credentials)

    assert context.user_id == "test_user"
    assert context.tenant_id == "test_tenant"


def test_get_current_context_rejects_missing_credentials():
    """
    Requests without a Bearer token should return HTTP 401.
    """

    with pytest.raises(HTTPException) as exc_info:
        get_current_context(None)

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Missing Authorization Bearer token."
    )


def test_get_current_context_rejects_invalid_token():
    """
    Invalid JWTs should return HTTP 401.
    """

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_context(credentials)

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Invalid access token."
    )


def test_admin_role_is_allowed():
    """
    An admin role should pass an admin-only authorization check.
    """

    assert has_required_role(
        current_role="admin",
        allowed_roles={"admin"},
    ) is True


def test_normal_user_is_rejected_from_admin_role():
    """
    A normal user should fail an admin-only authorization check.
    """

    assert has_required_role(
        current_role="user",
        allowed_roles={"admin"},
    ) is False