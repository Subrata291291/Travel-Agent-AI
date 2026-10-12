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
                # A Duffel city place can itself have a usable city IATA code;
                # keep it alongside its associated airport records.
                candidates.extend(
                    item for item in place["airports"] if isinstance(item, dict)
                )
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
                    "place_type": (
                        item.get("type")
                        if item is place
                        else "airport"
                    ) or place.get("type"),
                })
                city = item.get("city") or place.get("city")
                city_code = item.get("iata_city_code")
                if not city_code and isinstance(city, dict):
                    city_code = city.get("iata_code")
                if (
                    isinstance(city_code, str)
                    and re.fullmatch(r"[A-Za-z]{3}", city_code)
                    and city_code.upper() != code.upper()
                ):
                    city_name = (
                        city.get("name") if isinstance(city, dict) else None
                    ) or item.get("city_name") or place.get("city_name")
                    city_id = city.get("id") if isinstance(city, dict) else None
                    city_key = (city_code.upper(), str(city_name))
                    if city_key not in seen:
                        seen.add(city_key)
                        records.append({
                            "airport_name": city_name,
                            "city": city_name,
                            "country_code": country,
                            "iata_code": city_code.upper(),
                            "duffel_place_id": city_id,
                            "place_type": "city",
                        })
        return records

    def lookup(
        self,
        query: str,
        *,
        field: str | None = None,
        origin_country_code: str | None = None,
    ) -> dict[str, Any]:
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

        # Prefer a token-complete match. This lets "Delhi" match "New Delhi"
        # while excluding lexical lookalikes such as Déline and Delingha.
        place_query = original.split(",", maxsplit=1)[0].strip()
        normalized = self._normalize(place_query)
        query_tokens = set(normalized.split())
        exact = [
            item for item in all_records
            if normalized in {
                self._normalize(str(item.get("airport_name", ""))),
                self._normalize(str(item.get("city", ""))),
                self._normalize(str(item.get("iata_code", ""))),
            }
        ]
        exact_city = [
            item for item in exact
            if item.get("place_type") == "city"
            and normalized in {
                self._normalize(str(item.get("airport_name", ""))),
                self._normalize(str(item.get("city", ""))),
            }
        ]
        if exact_city:
            exact = exact_city
        lexical = exact or [
            item for item in all_records
            if query_tokens and any(
                query_tokens.issubset(set(self._normalize(str(item.get(field_name, ""))).split()))
                for field_name in ("airport_name", "city", "iata_code")
            )
        ]
        if lexical:
            all_records = lexical
        else:
            # Duffel's suggestions may include airports whose names merely
            # resemble the query (for example, Delhi, Canada). Resolve the
            # query's geography independently and use its country as a
            # relevance signal; airport codes still come exclusively from
            # Duffel. If geocoding is unavailable, retain the safe ambiguous
            # result rather than guessing.
            try:
                location = self.geocoding.search(original)
            except (requests.RequestException, ValueError, KeyError):
                location = None
            country_code = (
                location.get("country_code")
                if isinstance(location, dict)
                else None
            )
            if isinstance(country_code, str) and country_code:
                local_records = [
                    item for item in all_records
                    if str(item.get("country_code") or "").casefold()
                    == country_code.casefold()
                ]
                if local_records:
                    all_records = local_records

        # An unqualified destination in the same itinerary is more likely to
        # refer to the same country as the origin. Treat this only as a ranking
        # signal: if no such Duffel candidates exist, retain the other matches
        # and ask the user instead of silently forcing a country.
        if origin_country_code and "," not in original:
            same_country = [
                item for item in all_records
                if str(item.get("country_code") or "").casefold()
                == origin_country_code.casefold()
            ]
            if same_country:
                all_records = same_country

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
