"""Amadeus hotel list and hotel-offer search (search only)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.providers.amadeus.client import AmadeusClient
from app.providers.errors import ProviderRequestError
from app.schemas.hotel import HotelOption


class AmadeusHotelProvider:
    HOTEL_LIST_PATH = "/v1/reference-data/locations/hotels/by-geocode"
    HOTEL_OFFERS_PATH = "/v3/shopping/hotel-offers"
    MAX_HOTELS = 10

    def __init__(self, client: AmadeusClient | None = None):
        self.client = client or AmadeusClient()

    def search_hotels(
        self,
        destination: str,
        check_in_date: str,
        check_out_date: str,
        travellers: int = 1,
        budget_per_night: float | None = None,
        currency: str = "INR",
        *,
        resolved_destination: dict[str, Any] | None = None,
        room_quantity: int = 1,
    ) -> list[HotelOption]:
        try:
            check_in = date.fromisoformat(check_in_date)
            check_out = date.fromisoformat(check_out_date)
        except ValueError:
            raise ValueError("Hotel dates must use YYYY-MM-DD format.") from None
        nights = (check_out - check_in).days
        if nights <= 0 or travellers < 1 or room_quantity < 1:
            raise ValueError("Hotel search requires valid dates and at least one traveller.")
        if not resolved_destination:
            raise ValueError("A resolved destination with latitude and longitude is required.")
        try:
            latitude = float(resolved_destination["latitude"])
            longitude = float(resolved_destination["longitude"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("A resolved destination with latitude and longitude is required.") from None

        hotel_result = self.client.get(self.HOTEL_LIST_PATH, {
            "latitude": latitude,
            "longitude": longitude,
        })
        hotels = hotel_result.get("data", [])
        if not isinstance(hotels, list):
            raise ProviderRequestError("Amadeus returned an invalid hotel list.")
        hotel_ids = [
            item.get("hotelId") for item in hotels[: self.MAX_HOTELS]
            if isinstance(item, dict) and isinstance(item.get("hotelId"), str)
        ]
        if not hotel_ids:
            return []
        result = self.client.get(self.HOTEL_OFFERS_PATH, {
            "hotelIds": ",".join(hotel_ids),
            "adults": travellers,
            "checkInDate": check_in_date,
            "checkOutDate": check_out_date,
            "roomQuantity": room_quantity,
            "currency": currency,
        })
        entries = result.get("data", [])
        if not isinstance(entries, list):
            raise ProviderRequestError("Amadeus returned invalid hotel offers.")
        output: list[HotelOption] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            hotel = entry.get("hotel") or {}
            offers = entry.get("offers") or []
            for offer in offers:
                if not isinstance(offer, dict) or not isinstance(offer.get("id"), str):
                    continue
                price = offer.get("price") or {}
                try:
                    total = float(price["total"])
                except (KeyError, TypeError, ValueError):
                    continue
                if total < 0:
                    continue
                if budget_per_night is not None and total / nights > budget_per_night:
                    continue
                room = offer.get("room") or {}
                estimated = room.get("typeEstimated") or {}
                description = room.get("description") or {}
                cancellation = (offer.get("policies") or {}).get("cancellation") or {}
                supplier_id = offer["id"]
                hotel_id = hotel.get("hotelId") or ""
                output.append(HotelOption(
                    # Keep the supplier offer ID canonical for selection.
                    hotel_id=supplier_id,
                    supplier_offer_id=supplier_id,
                    supplier_hotel_id=hotel_id or None,
                    total_price=total,
                    provider_details={
                        "room_type": room.get("type") or estimated.get("category"),
                        "room_description": description.get("text") if isinstance(description, dict) else None,
                        "board_type": offer.get("boardType"),
                        "cancellation_policy": cancellation,
                        "is_test_data": "test.api.amadeus.com" in self.client.base_url,
                        "room_quantity": room_quantity,
                    },
                    name=hotel.get("name") or "Hotel",
                    destination=destination,
                    provider="Amadeus",
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    price_per_night=round(total / nights, 2),
                    currency=price.get("currency") or currency,
                    travellers=travellers,
                    rating=None,
                    amenities=[],
                ))
        return output
