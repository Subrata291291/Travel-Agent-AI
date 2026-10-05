from datetime import datetime, timedelta
from typing import List

from langchain_core.tools import tool

from app.schemas.transport import TransportOption


@tool
def search_buses(
    origin: str,
    destination: str,
    departure_date: str,
    travellers: int = 1,
) -> List[TransportOption]:
    """
    Search available bus options between an origin and destination.

    This is currently a mock transport provider used to validate
    the transport tool contract and agent workflow.
    """

    departure = datetime.fromisoformat(
        f"{departure_date}T20:00:00"
    )

    arrival = departure + timedelta(minutes=1440)

    return [
        TransportOption(
            mode="bus",
            provider="Mock Bus Provider",
            origin=origin,
            destination=destination,
            departure_time=departure.isoformat(),
            arrival_time=arrival.isoformat(),
            duration_minutes=1440,
            price=1800.0 * travellers,
            currency="INR",
        )
    ]