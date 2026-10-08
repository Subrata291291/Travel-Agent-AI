"""Resolve user-entered places to Duffel-compatible IATA codes."""

from __future__ import annotations

import re
import unicodedata
from app.providers.duffel.client import DuffelClient


class AirportResolver:
    """Use Duffel Places Suggestions without guessing among airports."""

    def __init__(self, client: DuffelClient | None = None) -> None:
        self.client = client or DuffelClient()

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        ascii_value = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()

    def resolve(self, place: str) -> str:
        """Return a validated IATA code for a city, airport name, or code."""
        if not place or not place.strip():
            raise ValueError("Please provide a departure and arrival city or airport.")

        query = place.strip()
        if re.fullmatch(r"[A-Za-z]{3}", query):
            return query.upper()

        response = self.client.get_sync(
            "/places/suggestions",
            params={"query": query},
        )
        data = response.get("data", [])
        if not isinstance(data, list):
            data = []

        candidates = [
            candidate
            for candidate in data
            if isinstance(candidate, dict)
            and candidate.get("type") in {"city", "airport"}
            and isinstance(candidate.get("iata_code"), str)
            and re.fullmatch(r"[A-Za-z]{3}", candidate["iata_code"])
        ]
        if not candidates:
            raise ValueError(f"No airport or city code found for '{query}'.")

        # The first part is the place name when the user supplies a qualifier
        # such as "Springfield, Illinois". Duffel receives the full query.
        requested_name = self._normalize(query.split(",", maxsplit=1)[0])
        exact_cities = [
            candidate
            for candidate in candidates
            if candidate.get("type") == "city"
            and self._normalize(candidate.get("name", "")) == requested_name
        ]
        if len(exact_cities) == 1:
            return exact_cities[0]["iata_code"].upper()

        exact_airports = [
            candidate
            for candidate in candidates
            if candidate.get("type") == "airport"
            and self._normalize(candidate.get("name", "")) == requested_name
        ]
        if len(exact_airports) == 1:
            return exact_airports[0]["iata_code"].upper()

        exact = exact_cities or exact_airports
        if len(exact) > 1:
            candidates = exact
        elif len(candidates) == 1:
            return candidates[0]["iata_code"].upper()

        choices = ", ".join(
            f"{candidate.get('name', 'Unknown')} ({candidate['iata_code']})"
            for candidate in candidates[:5]
        )
        raise ValueError(
            f"'{query}' matches multiple places: {choices}. "
            "Please specify the city or airport, or provide its 3-letter IATA code."
        )
