from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TripPerception(BaseModel):
    """
    Structured understanding of a user's travel request.
    """

    intent: Literal[
        "plan_trip",
        "check_weather",
        "find_transport",
        "find_hotel",
        "find_restaurant",
        "book_trip",
        "question",
        "other",
    ] = Field(
        description="The primary intent of the user."
    )

    destination: Optional[str] = Field(
        default=None,
        description="Travel destination mentioned by the user."
    )

    start_date: Optional[str] = Field(
        default=None,
        description="Trip start date in YYYY-MM-DD format when known."
    )

    end_date: Optional[str] = Field(
        default=None,
        description="Trip end date in YYYY-MM-DD format when known."
    )

    duration_days: Optional[int] = Field(
        default=None,
        description="Number of days for the trip."
    )

    travellers: int = Field(
        default=1,
        ge=1,
        description="Number of travellers."
    )

    budget: Optional[float] = Field(
        default=None,
        ge=0,
        description="Maximum or approximate trip budget."
    )

    currency: str = Field(
        default="INR",
        description="Currency of the budget."
    )

    preferences: List[str] = Field(
        default_factory=list,
        description="Travel preferences, constraints, likes and dislikes."
    )