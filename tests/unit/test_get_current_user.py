import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_context, get_current_user
from app.auth.jwt import create_access_token
from app.database.connection import SessionLocal
from app.database.models import User


def create_credentials(
    user_id: str,
    tenant_id: str,
    role: str = "user",
) -> HTTPAuthorizationCredentials:
    """
    Create valid Bearer credentials for a test user.

    The role is included in the JWT to simulate a real login.
    However, get_current_user() should use the role stored
    in the database as the source of truth.
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


def create_test_user(
    user_id: str,
    tenant_id: str,
    role: str = "user",
    status: str = "active",
) -> User:
    """
    Create a temporary user directly in the test database.
    """

    db = SessionLocal()

    try:
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

    finally:
        db.close()


def delete_test_user(
    user_id: str,
    tenant_id: str,
) -> None:
    """
    Remove the temporary test user after the test.
    """

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(
                User.user_id == user_id,
                User.tenant_id == tenant_id,
            )
            .first()
        )

        if user is not None:
            db.delete(user)
            db.commit()

    finally:
        db.close()


def test_get_current_user_returns_database_role():
    """
    The database should be the source of truth for the user's role.

    Even if the JWT says 'user', if the database says 'admin',
    get_current_user() should return role='admin'.
    """

    user_id = "test_db_role_user"
    tenant_id = "test_db_role_tenant"

    create_test_user(
        user_id=user_id,
        tenant_id=tenant_id,
        role="admin",
        status="active",
    )

    try:
        credentials = create_credentials(
            user_id=user_id,
            tenant_id=tenant_id,
            role="user",
        )

        context = get_current_context(credentials)

        authenticated_user = get_current_user(context)

        assert authenticated_user.user_id == user_id
        assert authenticated_user.tenant_id == tenant_id
        assert authenticated_user.role == "admin"

    finally:
        delete_test_user(
            user_id=user_id,
            tenant_id=tenant_id,
        )


def test_get_current_user_rejects_unknown_user():
    """
    A valid JWT should not be enough.

    If the user does not exist in the database,
    authentication should fail with HTTP 401.
    """

    user_id = "unknown_test_user"
    tenant_id = "unknown_test_tenant"

    credentials = create_credentials(
        user_id=user_id,
        tenant_id=tenant_id,
    )

    context = get_current_context(credentials)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(context)

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Authenticated user was not found."
    )


def test_get_current_user_rejects_inactive_user():
    """
    An existing but inactive user should not be allowed
    to access protected resources.
    """

    user_id = "test_inactive_user"
    tenant_id = "test_inactive_tenant"

    create_test_user(
        user_id=user_id,
        tenant_id=tenant_id,
        role="user",
        status="inactive",
    )

    try:
        credentials = create_credentials(
            user_id=user_id,
            tenant_id=tenant_id,
        )

        context = get_current_context(credentials)

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(context)

        assert exc_info.value.status_code == 403
        assert (
            exc_info.value.detail
            == "User account is not active."
        )

    finally:
        delete_test_user(
            user_id=user_id,
            tenant_id=tenant_id,
        )