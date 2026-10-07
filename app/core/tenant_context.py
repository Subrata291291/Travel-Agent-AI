from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    """
    Trusted identity context for the current request.

    This object represents:
    - which tenant is making the request
    - which user is making the request

    API routes and services should use this context
    instead of reading identity information directly.
    """

    tenant_id: str
    user_id: str

    def __post_init__(self):
        """
        Validate the identity values at the application boundary.
        """

        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id cannot be empty.")

        if not self.user_id or not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

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