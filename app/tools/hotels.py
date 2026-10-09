from functools import lru_cache
from typing import List

from langchain_core.tools import tool

from app.providers.amadeus.hotels import AmadeusHotelProvider
from app.schemas.hotel import HotelOption


@lru_cache(maxsize=1)
def _hotel_provider() -> AmadeusHotelProvider:
    return AmadeusHotelProvider()


@tool
def search_hotels(destination: str, check_in_date: str, check_out_date: str,
                  travellers: int = 1, budget_per_night: float | None = None,
                  currency: str = "INR", room_quantity: int = 1,
                  resolved_destination: dict | None = None) -> List[HotelOption]:
    """Search live Amadeus hotel offers in the configured Amadeus environment."""
    return _hotel_provider().search_hotels(
        destination, check_in_date, check_out_date, travellers, budget_per_night, currency,
        resolved_destination=resolved_destination, room_quantity=room_quantity,
    )
