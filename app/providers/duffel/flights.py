from __future__ import annotations

from datetime import datetime
from typing import Any

from app.providers.duffel.airports import AirportLookupError, AirportResolver
from app.providers.duffel.client import DuffelClient
from app.schemas.transport import TransportOption


class DuffelFlightProvider:
    """
    Duffel implementation of the flight provider.

    Responsibilities:
    - Build Duffel flight-search requests
    - Call Duffel through DuffelClient
    - Convert Duffel offers into our application's TransportOption model

    Important:
    LangGraph does not need to know anything about Duffel's
    response structure.
    """

    def __init__(self, client: DuffelClient | None = None) -> None:
        self.client = client or DuffelClient()
        self.airports = AirportResolver(self.client)

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        travellers: int = 1,
        cabin_class: str = "economy",
        max_connections: int = 1,
    ) -> list[TransportOption]:
        """
        Search Duffel for one-way flight offers.

        origin and destination should be IATA airport/city codes,
        for example:

            CCU -> DEL
            LHR -> JFK
            NYC -> LAX
        """

        try:
            origin = self.airports.resolve(origin, field="origin")
        except AirportLookupError as exc:
            raise ValueError(f"Origin airport: {exc}") from exc
        try:
            destination = self.airports.resolve(destination, field="destination")
        except AirportLookupError as exc:
            raise ValueError(f"Destination airport: {exc}") from exc

        if travellers < 1:
            raise ValueError("travellers must be at least 1.")

        self._validate_date(departure_date)

        if cabin_class not in {
            "economy",
            "premium_economy",
            "business",
            "first",
        }:
            raise ValueError(
                "Invalid cabin_class. "
                "Use economy, premium_economy, business, or first."
            )

        if max_connections < 0:
            raise ValueError("max_connections cannot be negative.")

        passengers = [
            {"type": "adult"}
            for _ in range(travellers)
        ]

        payload = {
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date,
                    }
                ],
                "passengers": passengers,
                "cabin_class": cabin_class,
                "max_connections": max_connections,
            }
        }

        response = self.client.post_sync(
            "/air/offer_requests",
            json=payload,
        )

        data = response.get("data", {})

        if not isinstance(data, dict):
            return []

        offers = data.get("offers", [])

        if not isinstance(offers, list):
            return []

        return self._convert_offers_to_transport_options(
            offers=offers,
            travellers=travellers,
        )

    @staticmethod
    def _validate_date(departure_date: str) -> None:
        """
        Validate YYYY-MM-DD format.
        """

        try:
            datetime.strptime(departure_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                "departure_date must use YYYY-MM-DD format."
            ) from exc

    def _convert_offers_to_transport_options(
        self,
        offers: list[dict[str, Any]],
        travellers: int,
    ) -> list[TransportOption]:
        """
        Convert Duffel offers into our internal transport contract.

        Duffel's offer ID becomes our option_id.

        This is extremely important because later, when the user
        selects a flight, we need the real Duffel offer ID to
        revalidate/book that exact offer.
        """

        options: list[TransportOption] = []

        for offer in offers:
            try:
                option = self._convert_offer(
                    offer=offer,
                    travellers=travellers,
                )

                if option is not None:
                    options.append(option)

            except (KeyError, TypeError, ValueError):
                # Ignore malformed individual offers rather than
                # failing the complete search.
                continue

        return options

    def _convert_offer(
        self,
        offer: dict[str, Any],
        travellers: int,
    ) -> TransportOption | None:
        """
        Convert one Duffel offer into TransportOption.
        """

        offer_id = offer.get("id")

        if not offer_id:
            return None

        slices = offer.get("slices") or []

        if not slices:
            return None

        first_slice = slices[0]

        segments = first_slice.get("segments") or []

        if not segments:
            return None

        first_segment = segments[0]
        last_segment = segments[-1]

        departure_time = first_segment.get("departing_at")
        arrival_time = last_segment.get("arriving_at")

        if not departure_time or not arrival_time:
            return None

        departure_dt = self._parse_datetime(departure_time)
        arrival_dt = self._parse_datetime(arrival_time)

        duration_minutes = int(
            (arrival_dt - departure_dt).total_seconds() / 60
        )

        origin = (
            first_segment.get("origin", {}).get("iata_code")
            or first_slice.get("origin", {}).get("iata_code")
        )

        destination = (
            last_segment.get("destination", {}).get("iata_code")
            or first_slice.get("destination", {}).get("iata_code")
        )

        if not origin or not destination:
            return None

        operating_carrier = (
            first_segment.get("operating_carrier") or {}
        )

        provider_name = (
            operating_carrier.get("name")
            or operating_carrier.get("iata_code")
            or "Duffel Airline"
        )

        total_amount = offer.get("total_amount")

        if total_amount is None:
            return None

        try:
            total_price = float(total_amount)
        except (TypeError, ValueError):
            return None
        if total_price < 0:
            return None

        # Duffel reports the offer total for all passengers. The app's
        # BookingService treats option.price as a per-traveller fare.
        price = total_price / travellers

        currency = (
            offer.get("total_currency")
            or offer.get("base_currency")
            or "INR"
        )

        return TransportOption(
            mode="flight",
            provider=provider_name,
            origin=origin,
            destination=destination,
            departure_time=departure_dt.isoformat(),
            arrival_time=arrival_dt.isoformat(),
            duration_minutes=duration_minutes,
            price=price,
            travellers=travellers,
            total_price=total_price,
            currency=currency,
            option_id=offer_id,
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """
        Parse Duffel's ISO-8601 datetime.
        """

        normalized = value.replace("Z", "+00:00")

        return datetime.fromisoformat(normalized)
