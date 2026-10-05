from typing import Optional

from pydantic import BaseModel

from app.schemas.common import ResolvedDestination
from pydantic import BaseModel, Field

class ToolContext(BaseModel):
    """
    Shared context available to travel tools.

    This model contains only information that has already
    been resolved or explicitly provided by the workflow.
    """

    resolved_destination: Optional[ResolvedDestination] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    travellers: Optional[int] = None

    budget: Optional[float] = None
    currency: Optional[str] = None

    preferences: list[str] = Field(default_factory=list)