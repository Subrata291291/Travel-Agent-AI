"""Resolve flight places through Duffel's documented Places Suggestions API."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
import requests

from app.providers.duffel.client import DuffelAPIError, DuffelClient
from app.tools.geocoding import GeocodingTool


class AirportLookupError(ValueError):
    def __init__(self, message: str, *, field: str | None = None, ambiguous: bool = False):
        super().__init__(message)
        self.field = field
        self.ambiguous = ambiguous


class AirportResolver:
    """Resolve a city, airport name, or IATA code without guessing."""

    def __init__(
        self,
        client: DuffelClient | None = None,
        geocoding: GeocodingTool | None = None,
    ) -> None:
        self.client = client or DuffelClient()
        self.geocoding = geocoding or GeocodingTool()

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        ascii_value = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()

    @staticmethod
    def _airport_records(places: list[Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for place in places:
            if not isinstance(place, dict):
                continue
            candidates = [place]
            if place.get("type") == "city" and isinstance(place.get("airports"), list):
                candidates = [item for item in place["airports"] if isinstance(item, dict)]
            for item in candidates:
                code = item.get("iata_code")
                if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z]{3}", code):
                    continue
                name = item.get("name") or place.get("name")
                city = item.get("city_name") or place.get("city_name") or place.get("name")
                country = item.get("iata_country_code") or place.get("iata_country_code")
                key = (code.upper(), str(name))
                if key in seen:
                    continue
                seen.add(key)
                records.append({
                    "airport_name": name,
                    "city": city,
                    "country_code": country,
                    "iata_code": code.upper(),
                    "duffel_place_id": item.get("id"),
                })
        return records

    def lookup(self, query: str, *, field: str | None = None) -> dict[str, Any]:
        """Return resolved airport details, choices for ambiguity, or a safe error."""
        if not query or not query.strip():
            raise AirportLookupError("Please provide a city or airport.", field=field)

        original = query.strip()
        try:
            response = self.client.get_sync(
                "/places/suggestions", params={"query": original}
            )
            data = response.get("data", [])
            all_records = self._airport_records(data if isinstance(data, list) else [])
            # If a locality has no named Duffel place (for example Howrah),
            # locate the locality and ask Duffel for airports in that radius.
            # Airport names and IATA codes still come only from Duffel.
            if not all_records:
                location = self.geocoding.search(original)
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                if latitude is not None and longitude is not None:
                    nearby = self.client.get_sync(
                        "/places/suggestions",
                        params={
                            "lat": str(latitude),
                            "lng": str(longitude),
                            "rad": "60000",
                        },
                    )
                    nearby_data = nearby.get("data", [])
                    all_records = self._airport_records(
                        nearby_data if isinstance(nearby_data, list) else []
                    )
        except (DuffelAPIError, TimeoutError, OSError) as exc:
            raise AirportLookupError(
                "Airport lookup is temporarily unavailable. Please try again. ",
                field=field,
            ) from exc
        except requests.RequestException as exc:
            raise AirportLookupError(
                "Airport lookup is temporarily unavailable. Please try again.",
                field=field,
            ) from exc
        except ValueError as exc:
            raise AirportLookupError(
                f"No airport or city code found for '{original}'. Please try an airport or nearby city name.",
                field=field,
            ) from exc

        if not all_records:
            raise AirportLookupError(
                f"No airport or city code found for '{original}'. Please try an airport or nearby city name.",
                field=field,
            )

        normalized = self._normalize(original)
        exact = [
            item for item in all_records
            if normalized in {
                self._normalize(str(item.get("airport_name", ""))),
                self._normalize(str(item.get("city", ""))),
                self._normalize(str(item.get("iata_code", ""))),
            }
        ]
        if exact:
            all_records = exact

        unique = {item["iata_code"]: item for item in all_records}
        all_records = list(unique.values())
        if len(all_records) == 1:
            return {"status": "resolved", **all_records[0]}

        options = all_records[:6]
        choices = "; ".join(
            f"{item['airport_name']} ({item['city']}, {item['country_code']}) — {item['iata_code']}"
            for item in options
        )
        raise AirportLookupError(
            f"'{original}' matches multiple airports: {choices}. Which airport would you like?",
            field=field,
            ambiguous=True,
        )

    def resolve(self, place: str, *, field: str | None = None) -> str:
        """Compatibility method used by Duffel search; returns validated IATA code."""
        return self.lookup(place, field=field)["iata_code"]
