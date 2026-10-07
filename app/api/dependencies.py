from fastapi import Header, HTTPException

from app.core.tenant_context import TenantContext


def get_tenant_context(
    x_user_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> TenantContext:
    """
    Resolve the current user and tenant context.

    Development purpose:
    - Reads user_id and tenant_id from request headers.
    - Creates a TenantContext used by the application layer.

    Production:
    - These values should come from authenticated credentials
      such as a JWT or API key.
    - Clients must not be trusted to freely choose tenant_id.
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