from typing import List

from langchain_core.tools import tool

from app.schemas.hotel import HotelOption


@tool
def search_hotels(
    destination: str,
    check_in_date: str,
    check_out_date: str,
    travellers: int = 1,
    budget_per_night: float | None = None,
    currency: str = "INR",
) -> List[HotelOption]:
    """
    Search available hotels for a destination and date range.

    This is currently a mock hotel provider used to validate
    the hotel-search tool contract and agent workflow.

    The tool only searches and returns hotel options.
    It does NOT create bookings.
    """

    hotels = [
        HotelOption(
            hotel_id="HOTEL-1",
            name="Mock Mountain View Hotel",
            destination=destination,
            provider="Mock Hotel Provider",
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            price_per_night=3500.0,
            currency=currency,
            travellers=travellers,
            rating=4.3,
            amenities=[
                "WiFi",
                "Breakfast",
                "Parking",
            ],
        ),
        HotelOption(
            hotel_id="HOTEL-2",
            name="Mock Valley Resort",
            destination=destination,
            provider="Mock Hotel Provider",
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            price_per_night=5000.0,
            currency=currency,
            travellers=travellers,
            rating=4.6,
            amenities=[
                "WiFi",
                "Breakfast",
                "Mountain View",
                "Parking",
            ],
        ),
        HotelOption(
            hotel_id="HOTEL-3",
            name="Mock Budget Stay",
            destination=destination,
            provider="Mock Hotel Provider",
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            price_per_night=2200.0,
            currency=currency,
            travellers=travellers,
            rating=4.0,
            amenities=[
                "WiFi",
            ],
        ),
    ]

    if budget_per_night is not None:

        filtered = [
            hotel
            for hotel in hotels
            if hotel.price_per_night <= budget_per_night
        ]

        if filtered:
            return filtered

    return hotels