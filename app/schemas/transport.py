from typing import Literal

from pydantic import BaseModel, Field


class TransportOption(BaseModel):
    """
    A normalized transportation option.

    Flight, train, and bus providers should return
    their results using this common structure.
    """

    mode: Literal[
        "flight",
        "train",
        "bus",
    ]

    provider: str = Field(
        description="Name of the transportation provider."
    )

    origin: str = Field(
        description="Origin location."
    )

    destination: str = Field(
        description="Destination location."
    )

    departure_time: str = Field(
        description="Departure date and time."
    )

    arrival_time: str = Field(
        description="Arrival date and time."
    )

    duration_minutes: int = Field(
        ge=0,
        description="Total journey duration in minutes."
    )

    price: float = Field(
        ge=0,
        description="Price of the transportation option."
    )

    currency: str = Field(
        default="INR",
        description="Currency of the price."
    )