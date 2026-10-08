import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_context, get_current_user
from app.auth.jwt import create_access_token
from app.database.models import Tenant, User


def create_credentials(
    user_id: str,
    tenant_id: str,
    role: str = "user",
) -> HTTPAuthorizationCredentials:
    """
    Create valid Bearer credentials for a test user.

    The role is included in the JWT to simulate a real login.

    Important:
    get_current_user() should NOT trust the role from the JWT.
    The database remains the source of truth for the current role.
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


def create_test_tenant(
    db: Session,
    tenant_id: str,
) -> Tenant:
    """
    Create a tenant inside the test database.

    User.tenant_id has a foreign-key relationship with tenants,
    so the tenant must exist before creating the user.
    """

    tenant = Tenant(
        tenant_id=tenant_id,
        name=f"Test Tenant {tenant_id}",
        slug=tenant_id,
        status="active",
    )

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return tenant


def create_test_user(
    db: Session,
    user_id: str,
    tenant_id: str,
    role: str = "user",
    status: str = "active",
) -> User:
    """
    Create a temporary user directly in the isolated test database.
    """

    user = User(
        user_id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@example.com",
        role=role,
        status=status,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def test_get_current_user_returns_database_role(test_db):
    """
    The database should be the source of truth for the user's role.

    Even if the JWT says 'user', if the database says 'admin',
    get_current_user() should return role='admin'.
    """

    user_id = "test_db_role_user"
    tenant_id = "test_db_role_tenant"

    create_test_tenant(
        db=test_db,
        tenant_id=tenant_id,
    )

    create_test_user(
        db=test_db,
        user_id=user_id,
        tenant_id=tenant_id,
        role="admin",
        status="active",
    )

    credentials = create_credentials(
        user_id=user_id,
        tenant_id=tenant_id,
        role="user",
    )

    context = get_current_context(credentials)

    authenticated_user = get_current_user(
        context=context,
        db=test_db,
    )

    assert authenticated_user.user_id == user_id
    assert authenticated_user.tenant_id == tenant_id

    # Important assertion:
    # JWT says "user", but DB says "admin".
    assert authenticated_user.role == "admin"


def test_get_current_user_rejects_unknown_user(test_db):
    """
    A valid JWT should not be enough.

    If the user does not exist in the database,
    authentication should fail with HTTP 401.
    """

    user_id = "unknown_test_user"
    tenant_id = "unknown_test_tenant"

    create_test_tenant(
        db=test_db,
        tenant_id=tenant_id,
    )

    credentials = create_credentials(
        user_id=user_id,
        tenant_id=tenant_id,
    )

    context = get_current_context(credentials)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(
            context=context,
            db=test_db,
        )

    assert exc_info.value.status_code == 401

    assert (
        exc_info.value.detail
        == "Authenticated user was not found."
    )


def test_get_current_user_rejects_inactive_user(test_db):
    """
    An existing but inactive user should not be allowed
    to access protected resources.
    """

    user_id = "test_inactive_user"
    tenant_id = "test_inactive_tenant"

    create_test_tenant(
        db=test_db,
        tenant_id=tenant_id,
    )

    create_test_user(
        db=test_db,
        user_id=user_id,
        tenant_id=tenant_id,
        role="user",
        status="inactive",
    )

    credentials = create_credentials(
        user_id=user_id,
        tenant_id=tenant_id,
    )

    context = get_current_context(credentials)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(
            context=context,
            db=test_db,
        )

    assert exc_info.value.status_code == 403

    assert (
        exc_info.value.detail
        == "User account is not active."
    )