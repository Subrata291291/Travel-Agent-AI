from app.tools.geocoding import GeocodingTool


class DestinationResolver:

    def __init__(self):
        self.geocoding = GeocodingTool()

    def resolve(
        self,
        location: str,
        country_code: str | None = None,
    ) -> dict:

        candidates = (
            self.geocoding.search_candidates(
                location,
                country_code,
            )
        )

        if not candidates:
            return {
                "status": "not_found",
                "location": location,
                "candidates": [],
            }

        # ----------------------------------------------------
        # Exact candidate matching
        # ----------------------------------------------------

        normalized_location = (
            location.strip().lower()
        )

        exact_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("name", "")
            .strip()
            .lower()
            == normalized_location
        ]

        # ----------------------------------------------------
        # If the query contains a region/country,
        # Open-Meteo may return a single strong match.
        # ----------------------------------------------------

        if len(candidates) == 1:

            return {
                "status": "resolved",
                "location": candidates[0],
                "candidates": candidates,
            }

        # ----------------------------------------------------
        # Try to identify a strong exact geographic match.
        # ----------------------------------------------------

        if exact_candidates:

            unique_coordinates = {
                (
                    candidate.get("latitude"),
                    candidate.get("longitude"),
                )
                for candidate in exact_candidates
            }

            if len(unique_coordinates) == 1:

                return {
                    "status": "resolved",
                    "location": exact_candidates[0],
                    "candidates": candidates,
                }

        # ----------------------------------------------------
        # Multiple plausible locations
        # ----------------------------------------------------

        return {
            "status": "ambiguous",
            "location": location,
            "candidates": candidates,
        }