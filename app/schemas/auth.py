from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        description="User's login email address."
    )

    password: str = Field(
        min_length=8,
        description="User's account password."
    )


class LoginResponse(BaseModel):
    access_token: str = Field(
        description="JWT access token."
    )

    token_type: str = Field(
        default="bearer",
        description="Authentication scheme."
    )

    expires_in: int = Field(
        description="Token lifetime in seconds."
    )

    user_id: str = Field(
        description="Authenticated user's ID."
    )

    tenant_id: str = Field(
        description="Tenant associated with the authenticated user."
    )

    role: str = Field(
        description="Authenticated user's role."
    )


class CurrentUserResponse(BaseModel):
    user_id: str = Field(
        description="Authenticated user's ID."
    )

    tenant_id: str = Field(
        description="Tenant associated with the authenticated user."
    )

    role: str = Field(
        description="Current role of the authenticated user."
    )