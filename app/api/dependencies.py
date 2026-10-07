from fastapi import Header, HTTPException

from app.core.tenant_context import TenantContext


def get_tenant_context(
    x_user_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> TenantContext:
    """
    Resolve the current request identity.

    Development implementation:
        X-User-ID
        X-Tenant-ID

    Production authentication can later replace this
    implementation with JWT/API-key based identity resolution.

    The rest of the application should continue receiving
    TenantContext and should not care how authentication works.
    """

    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing X-User-ID header.",
        )

    if not x_tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Tenant-ID header.",
        )

    try:
        return TenantContext(
            tenant_id=x_tenant_id,
            user_id=x_user_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc