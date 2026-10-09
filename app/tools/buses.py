from typing import List

from langchain_core.tools import tool

from app.providers.busbud_adapter import BusbudProvider
from app.schemas.transport import TransportOption


@tool
def search_buses(origin: str, destination: str, departure_date: str,
                 travellers: int = 1) -> List[TransportOption]:
    """Search Busbud only when the official partner integration is enabled."""
    return BusbudProvider().search_buses(origin=origin, destination=destination,
                                        departure_date=departure_date, travellers=travellers)
