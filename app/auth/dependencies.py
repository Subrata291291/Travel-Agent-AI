from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.auth.jwt import decode_access_token
from app.core.tenant_context import TenantContext


# Reads:
# Authorization: Bearer <JWT>
bearer_scheme = HTTPBearer(
    auto_error=False,
)


def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> TenantContext:
    """
    Resolve the authenticated user's TenantContext
    from a verified JWT access token.

    This is the JWT authentication boundary.

    Routes and services should not decode JWTs directly.
    """

    # -----------------------------------------
    # 1. Authorization header check
    # -----------------------------------------

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
        )

    # -----------------------------------------
    # 2. Extract JWT
    # -----------------------------------------

    token = credentials.credentials

    # -----------------------------------------
    # 3. Decode and verify JWT
    # -----------------------------------------

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

    # -----------------------------------------
    # 4. Extract trusted identity claims
    # -----------------------------------------

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

    # -----------------------------------------
    # 5. Convert JWT identity into
    #    application TenantContext
    # -----------------------------------------

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