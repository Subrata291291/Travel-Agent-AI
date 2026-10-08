from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.core.tenant_context import TenantContext
from app.database.connection import SessionLocal
from app.database.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TenantContext:
    """
    Validate the JWT and build the authenticated user's identity context.

    This dependency validates:
    - Bearer authentication
    - JWT signature
    - JWT expiration
    - user identity
    - tenant identity

    It does not perform role authorization.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)

    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
        ) from exc

    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        ) from exc

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing user identity.",
        )

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing tenant identity.",
        )

    try:
        return TenantContext(
            user_id=user_id,
            tenant_id=tenant_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def get_current_user(
    context: TenantContext = Depends(get_current_context),
) -> TenantContext:
    """
    Resolve the authenticated user from the database.

    The JWT provides the identity:
        user_id + tenant_id

    The database remains the source of truth for:
        - account status
        - current role

    This prevents an old JWT from retaining privileges after
    a user's role or account status has been changed.
    """

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(
                User.user_id == context.user_id,
                User.tenant_id == context.tenant_id,
            )
            .first()
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user was not found.",
            )

        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active.",
            )

        return TenantContext(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            role=user.role,
        )

    finally:
        db.close()

def has_required_role(
    current_role: str,
    allowed_roles: set[str],
) -> bool:
    """
    Check whether the current role is allowed.

    This function contains the pure authorization decision
    and is intentionally independent of FastAPI.
    """

    return current_role.strip().lower() in allowed_roles

def require_roles(*allowed_roles: str) -> Callable:
    """
    Create a FastAPI dependency that allows only specific roles.

    Examples:

        Depends(require_roles("admin"))

    or:

        Depends(require_roles("admin", "manager"))
    """

    if not allowed_roles:
        raise ValueError("At least one allowed role must be provided.")

    normalized_roles = {
        role.strip().lower()
        for role in allowed_roles
        if role and role.strip()
    }

    if not normalized_roles:
        raise ValueError("Allowed roles cannot be empty.")

    def role_checker(
        context: TenantContext = Depends(get_current_user),
    ) -> TenantContext:
        if not has_required_role(
            current_role=context.role,
            allowed_roles=normalized_roles,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )

        return context

    return role_checker