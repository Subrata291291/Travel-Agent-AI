"""
Tenant context for the Travel Agent SaaS application.

A tenant represents one customer/company using the SaaS platform.

The context is intentionally small and framework-independent so it can
later be used by FastAPI, background workers, CLI scripts, or tests.
"""


class TenantContext:
    """
    Holds the tenant identity for the current application workflow.

    Example:

        context = TenantContext(
            tenant_id="tenant_demo",
            user_id="user_demo",
        )

    Services and repositories can use this context to ensure that
    data is accessed only within the correct tenant.
    """

    def __init__(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")

        if not user_id:
            raise ValueError("user_id is required")

        self.tenant_id = tenant_id
        self.user_id = user_id

    def __repr__(self) -> str:
        return (
            f"TenantContext("
            f"tenant_id={self.tenant_id!r}, "
            f"user_id={self.user_id!r}"
            f")"
        )