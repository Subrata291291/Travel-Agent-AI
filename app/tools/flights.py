from datetime import datetime, timedelta
from typing import List

from langchain_core.tools import tool

from app.schemas.transport import TransportOption


@tool
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    travellers: int = 1,
) -> List[TransportOption]:
    """
    Search available flight options between an origin and destination.

    This is currently a mock transport provider used to validate
    the transport tool contract and agent workflow.
    """

    departure = datetime.fromisoformat(
        f"{departure_date}T09:00:00"
    )
    

    arrival = departure + timedelta(minutes=150)

    return [
        TransportOption(
            mode="flight",
            provider="Mock Airline Provider",
            origin=origin,
            destination=destination,
            departure_time=departure.isoformat(),
            arrival_time=arrival.isoformat(),
            duration_minutes=150,
            price=6500.0 * travellers,
            currency="INR",
            option_id="FLIGHT-1",
        )
    ]