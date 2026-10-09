from uuid import uuid4
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
)
from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
from app.config.settings import settings
from app.core.tenant_context import TenantContext
from app.database.connection import get_db
from app.database.models import Tenant, User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RegistrationRequest,
    ProfileUpdateRequest,
    EmailChangeRequest,
    PasswordChangeRequest,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegistrationRequest, db: Session = Depends(get_db)):
    """Create an individual tenant and its first user, then return a JWT."""
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required.")

    email = str(request.email).strip().lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    account_id = uuid4().hex
    tenant = Tenant(tenant_id=account_id, name=name, slug=f"account-{account_id}", status="active")
    user = User(
        user_id=account_id,
        tenant_id=account_id,
        email=email,
        password_hash=hash_password(request.password),
        name=name,
        role="user",
        status="active",
    )
    try:
        db.add_all([tenant, user])
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from None

    return LoginResponse(
        access_token=create_access_token(user_id=user.user_id, tenant_id=user.tenant_id, role=user.role),
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
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
        .filter(func.lower(User.email) == str(request.email).strip().lower())
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
        name=context.name,
        email=context.email,
        profile_picture_data=context.profile_picture_data,
    )


@router.patch("/profile", response_model=CurrentUserResponse)
def update_profile(
    request: ProfileUpdateRequest,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == context.user_id,
        User.tenant_id == context.tenant_id,
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User was not found.")

    if "name" in request.model_fields_set:
        name = (request.name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be empty.")
        user.name = name

    if "profile_picture_data" in request.model_fields_set:
        image_data = request.profile_picture_data
        if image_data is not None:
            try:
                header, encoded = image_data.split(",", 1)
                if header not in {
                    "data:image/jpeg;base64", "data:image/png;base64",
                    "data:image/webp;base64",
                }:
                    raise ValueError
                decoded = base64.b64decode(encoded, validate=True)
                signature_valid = (
                    (header == "data:image/jpeg;base64" and decoded.startswith(b"\xff\xd8\xff"))
                    or (header == "data:image/png;base64" and decoded.startswith(b"\x89PNG\r\n\x1a\n"))
                    or (header == "data:image/webp;base64" and decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP")
                )
                if not decoded or len(decoded) > 2 * 1024 * 1024 or not signature_valid:
                    raise ValueError
            except (ValueError, binascii.Error):
                raise HTTPException(
                    status_code=422,
                    detail="Profile photo must be a valid JPEG, PNG, or WebP image up to 2 MB.",
                ) from None
        user.profile_picture_data = image_data

    db.commit()
    db.refresh(user)
    return CurrentUserResponse(
        user_id=user.user_id, tenant_id=user.tenant_id, role=user.role,
        name=user.name, email=user.email,
        profile_picture_data=user.profile_picture_data,
    )


@router.patch("/email", response_model=CurrentUserResponse)
def change_email(
    request: EmailChangeRequest,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == context.user_id,
        User.tenant_id == context.tenant_id,
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User was not found.")
    if not verify_password(request.current_password, user.password_hash or ""):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    email = str(request.new_email).strip().lower()
    duplicate = db.query(User).filter(
        func.lower(User.email) == email,
        User.user_id != user.user_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That email address is already in use.")
    user.email = email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That email address is already in use.") from None
    db.refresh(user)
    return CurrentUserResponse(
        user_id=user.user_id, tenant_id=user.tenant_id, role=user.role,
        name=user.name, email=user.email,
        profile_picture_data=user.profile_picture_data,
    )


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: PasswordChangeRequest,
    context: TenantContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == context.user_id,
        User.tenant_id == context.tenant_id,
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User was not found.")
    if not verify_password(request.current_password, user.password_hash or ""):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if request.current_password == request.new_password:
        raise HTTPException(status_code=422, detail="New password must be different from the current password.")
    user.password_hash = hash_password(request.new_password)
    db.commit()
