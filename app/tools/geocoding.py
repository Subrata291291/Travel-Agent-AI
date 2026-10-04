import requests


class GeocodingTool:
    """
    Converts a place name into geographic coordinates
    using Open-Meteo's geocoding API.
    """

    BASE_URL = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    def search(
        self,
        location: str,
        country_code: str | None = None,
    ) -> dict:

        params = {
            "name": location,
            "count": 10,
            "language": "en",
            "format": "json",
        }

        if country_code:
            params["countryCode"] = country_code.upper()

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        results = data.get("results", [])

        if not results:
            raise ValueError(
                f"Location not found: {location}"
            )

        exact_matches = [
            result
            for result in results
            if result.get("name", "").lower()
            == location.strip().lower()
        ]

        if exact_matches:
            results = exact_matches

        best_match = results[0]

        return {
            "name": best_match.get("name"),
            "latitude": best_match.get("latitude"),
            "longitude": best_match.get("longitude"),
            "country": best_match.get("country"),
            "country_code": best_match.get(
                "country_code"
            ),
            "admin1": best_match.get("admin1"),
            "timezone": best_match.get("timezone"),
        }

    def search_candidates(
        self,
        location: str,
        country_code: str | None = None,
    ) -> list[dict]:

        params = {
            "name": location,
            "count": 10,
            "language": "en",
            "format": "json",
        }

        if country_code:
            params["countryCode"] = country_code.upper()

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        results = data.get("results", [])

        candidates = []

        for result in results:

            candidates.append(
                {
                    "name": result.get("name"),
                    "latitude": result.get(
                        "latitude"
                    ),
                    "longitude": result.get(
                        "longitude"
                    ),
                    "country": result.get(
                        "country"
                    ),
                    "country_code": result.get(
                        "country_code"
                    ),
                    "admin1": result.get(
                        "admin1"
                    ),
                    "admin2": result.get(
                        "admin2"
                    ),
                    "timezone": result.get(
                        "timezone"
                    ),
                }
            )

        return candidates