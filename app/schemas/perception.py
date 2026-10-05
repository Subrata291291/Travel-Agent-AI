from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TripPerception(BaseModel):
    """
    Structured representation of the user's travel request.

    Role:
    - Converts natural-language input into predictable application data.
    - Used by the perception agent before planning or booking.
    - The application uses this schema for routing decisions.
    """

    # ========================================================
    # USER INTENT
    # ========================================================

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

    # ========================================================
    # DESTINATION
    # ========================================================

    destination: Optional[str] = Field(
        default=None,
        description="Travel destination mentioned by the user.",
    )

    # ========================================================
    # TRAVEL DATES
    # ========================================================

    start_date: Optional[str] = Field(
        default=None,
        description=(
            "Trip start date in YYYY-MM-DD format "
            "when known."
        ),
    )

    end_date: Optional[str] = Field(
        default=None,
        description=(
            "Trip end date in YYYY-MM-DD format "
            "when known."
        ),
    )

    duration_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of days for the trip.",
    )

    # ========================================================
    # TRAVELLERS
    # ========================================================

    travellers: int = Field(
        default=1,
        ge=1,
        description="Number of travellers.",
    )

    # ========================================================
    # BUDGET
    # ========================================================

    budget: Optional[float] = Field(
        default=None,
        ge=0,
        description=(
            "Maximum or approximate trip budget."
        ),
    )

    currency: Optional[str] = Field(
        default="INR",
        description="Currency of the budget.",
    )

    # ========================================================
    # PREFERENCES
    # ========================================================

    preferences: Optional[List[str]] = Field(
        default_factory=list,
        description=(
            "Travel preferences, constraints, "
            "likes and dislikes."
        ),
    )

    # ========================================================
    # TRANSPORT MODE
    # ========================================================

    transport_mode: Literal[
        "flight",
        "train",
        "bus",
        "any",
        "unknown",
    ] = Field(
        default="unknown",
        description=(
            "Preferred transportation mode. "
            "Use 'flight' for flights, "
            "'train' for trains, "
            "'bus' for buses, "
            "'any' when user wants to compare "
            "all transportation modes, and "
            "'unknown' when no transportation mode "
            "has been specified."
        ),
    )

    # ========================================================
    # SELECTED TRANSPORT OPTION
    # ========================================================

    selected_option_id: Optional[str] = Field(
        default=None,
        description=(
            "Exact transport option ID selected by "
            "the user, such as FLIGHT-1, TRAIN-1, "
            "or BUS-1."
        ),
    )

    # ========================================================
    # BOOKING CONFIRMATION
    # ========================================================

    confirmation: Literal[
        "yes",
        "no",
        "unknown",
    ] = Field(
        default="unknown",
        description=(
            "User's explicit confirmation for a pending "
            "booking. Use 'yes' when the user explicitly "
            "confirms the booking, 'no' when the user "
            "explicitly rejects/cancels it, and 'unknown' "
            "when there is no clear confirmation."
        ),
    )