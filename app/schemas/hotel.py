from typing import List

from pydantic import BaseModel, Field


class HotelOption(BaseModel):
    """
    Represents one hotel search result.

    This schema describes a hotel option returned by a
    hotel-search provider.

    It does NOT represent a confirmed booking.
    """

    hotel_id: str = Field(
        description="Unique identifier for the hotel option."
    )

    name: str = Field(
        description="Hotel name."
    )

    destination: str = Field(
        description="Hotel destination."
    )

    provider: str = Field(
        description="Hotel provider or supplier."
    )

    check_in_date: str = Field(
        description="Hotel check-in date."
    )

    check_out_date: str = Field(
        description="Hotel check-out date."
    )

    price_per_night: float = Field(
        ge=0,
        description="Price per night."
    )

    currency: str = Field(
        default="INR",
        description="Price currency."
    )

    travellers: int = Field(
        default=1,
        ge=1,
        description="Number of travellers."
    )

    rating: float | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Hotel rating from 0 to 5."
    )

    amenities: List[str] = Field(
        default_factory=list,
        description="Available hotel amenities."
    )