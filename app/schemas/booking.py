from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BookingRequest(BaseModel):
    """
    Input contract for creating a booking.

    Role:
    - Defines the trusted information required by the booking layer.
    - Keeps booking logic independent from the LLM.
    """

    user_id: str
    session_id: str

    option_id: str = Field(
        min_length=1
    )

    travellers: int = Field(
        default=1,
        ge=1,
    )


class BookingResponse(BaseModel):
    """
    Output contract returned after a successful booking.

    Role:
    - Gives the application a stable booking response.
    - Prevents database models from leaking into the agent/API layer.
    """

    booking_id: str

    user_id: str
    session_id: str

    option_id: str

    status: Literal[
        "confirmed",
        "failed",
    ]

    mode: str
    provider: str

    origin: str
    destination: str

    departure_time: str
    arrival_time: str

    duration_minutes: int

    price: float
    currency: str

    travellers: int
    total_price: float

    created_at: datetime