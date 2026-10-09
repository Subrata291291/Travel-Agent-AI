from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    """
    Trusted identity context for the current request.

    This object represents:
    - which tenant is making the request
    - which user is making the request
    - which role the user has

    API routes and services should use this context
    instead of reading identity information directly.
    """

    tenant_id: str
    user_id: str
    role: str = "user"
    name: str | None = None
    email: str | None = None

    def __post_init__(self):
        """
        Validate and normalize identity values at the application boundary.
        """

        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id cannot be empty.")

        if not self.user_id or not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.role or not self.role.strip():
            raise ValueError("role cannot be empty.")

        # Normalize surrounding whitespace.
        object.__setattr__(
            self,
            "tenant_id",
            self.tenant_id.strip(),
        )

        object.__setattr__(
            self,
            "user_id",
            self.user_id.strip(),
        )

        # Normalize role for consistent authorization checks.
        object.__setattr__(
            self,
            "role",
            self.role.strip().lower(),
        )
