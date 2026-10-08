from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
)
from app.auth.jwt import create_access_token
from app.auth.password import verify_password
from app.config.settings import settings
from app.core.tenant_context import TenantContext
from app.database.connection import get_db
from app.database.models import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate a user and return a JWT access token.

    Authentication flow:

        email + password
            ↓
        find user
            ↓
        check account status
            ↓
        verify bcrypt password
            ↓
        create JWT
            ↓
        return authentication response

    Database access is provided through FastAPI dependency
    injection so tests can replace the production database
    with an isolated test database.
    """

    # ----------------------------------------------------
    # 1. Find user by email
    # ----------------------------------------------------

    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    # ----------------------------------------------------
    # 2. Do not reveal whether the email exists
    # ----------------------------------------------------

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # ----------------------------------------------------
    # 3. Check account status
    # ----------------------------------------------------

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    # ----------------------------------------------------
    # 4. Make sure a password has been configured
    # ----------------------------------------------------

    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password has not been configured for this account.",
        )

    # ----------------------------------------------------
    # 5. Verify password
    # ----------------------------------------------------

    if not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # ----------------------------------------------------
    # 6. Create JWT
    # ----------------------------------------------------

    access_token = create_access_token(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
    )

    # ----------------------------------------------------
    # 7. Calculate token lifetime
    # ----------------------------------------------------

    expires_in = settings.jwt_expire_minutes * 60

    # ----------------------------------------------------
    # 8. Return authentication response
    # ----------------------------------------------------

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_me(
    context: TenantContext = Depends(get_current_user),
):
    """
    Return the currently authenticated user's identity.

    The identity and role come from the database-backed
    get_current_user dependency.

    The JWT identifies the user, while the database remains
    the source of truth for the user's current account status
    and role.
    """

    return CurrentUserResponse(
        user_id=context.user_id,
        tenant_id=context.tenant_id,
        role=context.role,
    )