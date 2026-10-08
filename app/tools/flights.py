from functools import lru_cache
from typing import List

from langchain_core.tools import tool

from app.providers.duffel.flights import DuffelFlightProvider
from app.schemas.transport import TransportOption


@lru_cache(maxsize=1)
def _flight_provider() -> DuffelFlightProvider:
    """Initialize Duffel only when a flight search is requested."""
    return DuffelFlightProvider()


@tool
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    travellers: int = 1,
) -> List[TransportOption]:
    """
    Search available flight options using Duffel.

    Args:
        origin:
            City/airport name or 3-letter IATA code, for example Kolkata or CCU.
        destination:
            City/airport name or 3-letter IATA code, for example Delhi or DEL.
        departure_date:
            Departure date in YYYY-MM-DD format.
        travellers:
            Number of adult travellers.

    Returns:
        A list of real flight options returned by Duffel. Prices are
        normalized to per-traveller price and include total_price for the
        complete party when Duffel provides an offer.
    """

    return _flight_provider().search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        travellers=travellers,
    )
