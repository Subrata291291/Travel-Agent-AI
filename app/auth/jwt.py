from datetime import datetime, timedelta, timezone

import jwt

from app.config.settings import settings


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str = "user",
) -> str:
    """
    Create a signed JWT access token.

    The token contains the identity information required
    by the application to build a TenantContext.
    """

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes=settings.jwt_expire_minutes
    )

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return token


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.

    Raises:
        jwt.InvalidTokenError:
            If the token is invalid, expired, malformed,
            or has an invalid signature.
    """

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    return payload