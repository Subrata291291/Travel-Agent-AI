from typing import Literal

from pydantic import BaseModel, Field


class TransportOption(BaseModel):
    option_id: str
    mode: Literal["flight", "train", "bus"]
    provider: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration_minutes: int = Field(ge=0)
    price: float = Field(ge=0)
    travellers: int | None = Field(default=None, ge=1)
    total_price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="INR")
