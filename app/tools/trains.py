from datetime import datetime, timedelta
from typing import List

from langchain_core.tools import tool

from app.schemas.transport import TransportOption


@tool
def search_trains(
    origin: str,
    destination: str,
    departure_date: str,
    travellers: int = 1,
) -> List[TransportOption]:
    """
    Search available train options between an origin and destination.

    This is currently a mock transport provider used to validate
    the transport tool contract and agent workflow.
    """

    departure = datetime.fromisoformat(
        f"{departure_date}T18:00:00"
    )

    arrival = departure + timedelta(
        minutes=1200
    )

    return [
        TransportOption(
            mode="train",
            provider="Mock Railway Provider",
            origin=origin,
            destination=destination,
            departure_time=departure.isoformat(),
            arrival_time=arrival.isoformat(),
            duration_minutes=1200,
            price=2100.0 * travellers,
            currency="INR",
            option_id="TRAIN-1",
        )
    ]