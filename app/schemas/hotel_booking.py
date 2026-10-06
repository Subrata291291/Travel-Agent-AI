from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HotelBookingRequest(BaseModel):
    """
    Trusted input required to create a hotel booking.

    The LLM does not directly create this object.
    The application builds it after the user explicitly
    confirms the selected hotel.
    """

    user_id: str
    session_id: str

    hotel_id: str = Field(
        min_length=1,
        description="Selected hotel option ID.",
    )

    travellers: int = Field(
        default=1,
        ge=1,
        description="Number of travellers.",
    )


class HotelBookingResponse(BaseModel):
    """
    Stable application-level response for a hotel booking.

    This is intentionally separate from the transport
    BookingResponse because hotel and transport have
    different domain attributes.
    """

    booking_id: str
    user_id: str
    session_id: str

    hotel_id: str
    hotel_name: str
    provider: str
    destination: str

    check_in_date: str
    check_out_date: str

    price_per_night: float
    currency: str

    travellers: int
    nights: int
    total_price: float

    status: Literal[
        "confirmed",
        "failed",
        "cancelled",
    ]

    created_at: datetime