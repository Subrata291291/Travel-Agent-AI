import unicodedata

from app.tools.geocoding import GeocodingTool


class DestinationResolver:

    def __init__(self):
        self.geocoding = GeocodingTool()

    @staticmethod
    def _normalize(value: str | None) -> str:
        value = unicodedata.normalize("NFKD", value or "")
        return "".join(
            character
            for character in value
            if not unicodedata.combining(character)
        ).casefold().strip()

    @staticmethod
    def _feature_rank(candidate: dict) -> int:
        feature_code = candidate.get("feature_code") or ""
        if feature_code == "PPLC":
            return 6
        if feature_code == "PPLA1":
            return 5
        if feature_code == "PPLA2":
            return 4
        if feature_code == "PPLA3":
            return 3
        if feature_code == "PPLA4":
            return 2
        if feature_code.startswith("PPL"):
            return 1
        return 0

    @classmethod
    def _matches_qualifiers(
        cls,
        candidate: dict,
        qualifiers: list[str],
    ) -> bool:
        hierarchy_fields = [
            cls._normalize(candidate.get(field))
            for field in (
                "admin1", "admin2", "admin3", "admin4",
                "country", "country_code",
            )
        ]
        normalized_hierarchy = " ".join(hierarchy_fields)
        return all(
            cls._normalize(qualifier) in hierarchy_fields
            or (
                " " in cls._normalize(qualifier)
                and cls._normalize(qualifier) in normalized_hierarchy
            )
            for qualifier in qualifiers
            if qualifier.strip()
        )

    @staticmethod
    def _deduplicate(candidates: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for candidate in candidates:
            key = (
                candidate.get("id")
                or (
                    candidate.get("latitude"),
                    candidate.get("longitude"),
                    candidate.get("name"),
                )
            )
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    def resolve(
        self,
        location: str,
        country_code: str | None = None,
    ) -> dict:
        query_parts = [part.strip() for part in location.split(",")]
        place_name = query_parts[0]
        qualifiers = [part for part in query_parts[1:] if part]

        candidates = self.geocoding.search_candidates(
            place_name,
            country_code,
        )

        # Support natural input such as "Goa India" when the provider
        # expects the place and qualifier to be comma-separated.
        if not candidates and len(query_parts) == 1:
            words = place_name.split()
            while len(words) > 1 and not candidates:
                qualifiers.insert(0, words.pop())
                place_name = " ".join(words)
                candidates = self.geocoding.search_candidates(
                    place_name,
                    country_code,
                )

        if not candidates:
            return {
                "status": "not_found",
                "location": location,
                "candidates": [],
            }

        candidates = [
            candidate
            for candidate in candidates
            if self._matches_qualifiers(candidate, qualifiers)
        ]

        if not candidates:
            return {
                "status": "not_found",
                "location": location,
                "candidates": [],
            }

        normalized_place = self._normalize(place_name)

        # Open-Meteo indexes populated places but may omit an administrative
        # region as a result. Search for places contained in an admin1 whose
        # name exactly matches the query (for example, Goa City in Goa).
        regional_candidates = self.geocoding.search_candidates(
            f"{place_name}, {place_name}",
            country_code,
        )
        regional_candidates = [
            candidate
            for candidate in regional_candidates
            if self._normalize(candidate.get("admin1")) == normalized_place
            and self._feature_rank(candidate) > 0
            and self._matches_qualifiers(candidate, qualifiers)
        ]

        if regional_candidates:
            admin1_ids = list(dict.fromkeys(
                candidate.get("admin1_id")
                for candidate in regional_candidates
                if candidate.get("admin1_id")
            ))
            for admin1_id in admin1_ids:
                administrative_area = self.geocoding.get_by_id(admin1_id)
                if (
                    self._normalize(administrative_area.get("name"))
                    == normalized_place
                    and self._normalize(
                        administrative_area.get("feature_code")
                    ) == "adm1"
                    and self._matches_qualifiers(
                        administrative_area,
                        qualifiers,
                    )
                ):
                    return {
                        "status": "resolved",
                        "location": administrative_area,
                        "candidates": [administrative_area],
                    }

            candidates = self._deduplicate(regional_candidates)
            # A place whose name begins with the queried region is the
            # clearest provider-backed representative of that region.
            candidates.sort(
                key=lambda candidate: (
                    not self._normalize(candidate.get("name")).startswith(
                        normalized_place
                    ),
                    -self._feature_rank(candidate),
                    -(candidate.get("population") or 0),
                    candidate.get("id") or 0,
                )
            )
            first = candidates[0]
            first_starts_with_query = self._normalize(
                first.get("name")
            ).startswith(normalized_place)
            second_starts_with_query = (
                len(candidates) > 1
                and self._normalize(candidates[1].get("name")).startswith(
                    normalized_place
                )
            )
            if first_starts_with_query and not second_starts_with_query:
                return {
                    "status": "resolved",
                    "location": first,
                    "candidates": candidates,
                }

        candidates = self._deduplicate(candidates)
        exact_candidates = [
            candidate
            for candidate in candidates
            if self._normalize(candidate.get("name")) == normalized_place
        ]

        if exact_candidates:
            exact_candidates.sort(
                key=lambda candidate: (
                    -self._feature_rank(candidate),
                    -(candidate.get("population") or 0),
                    candidate.get("id") or 0,
                )
            )
            if len(exact_candidates) == 1:
                return {
                    "status": "resolved",
                    "location": exact_candidates[0],
                    "candidates": exact_candidates,
                }

            best_rank = self._feature_rank(exact_candidates[0])
            next_rank = self._feature_rank(exact_candidates[1])
            if best_rank > next_rank:
                return {
                    "status": "resolved",
                    "location": exact_candidates[0],
                    "candidates": exact_candidates,
                }

            return {
                "status": "ambiguous",
                "location": location,
                "candidates": exact_candidates,
            }

        return {
            "status": "ambiguous",
            "location": location,
            "candidates": candidates,
        }
