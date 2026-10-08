from fastapi import APIRouter, Depends

from app.auth.dependencies import require_roles
from app.core.tenant_context import TenantContext


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get("/me")
def get_admin_context(
    context: TenantContext = Depends(require_roles("admin")),
):
    """
    Return the authenticated administrator's context.

    This endpoint is intentionally small.

    Its purpose is to verify that:
    1. the JWT is valid,
    2. the user exists,
    3. the user is active,
    4. the user's current database role is admin.
    """

    return {
        "message": "Admin access granted.",
        "user_id": context.user_id,
        "tenant_id": context.tenant_id,
        "role": context.role,
    }