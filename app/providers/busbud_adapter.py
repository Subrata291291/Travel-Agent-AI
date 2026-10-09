"""Busbud partner adapter boundary. No API calls without official docs."""

from app.providers.errors import ProviderNotConfiguredError
from app.schemas.transport import TransportOption


class BusbudProvider:
    def search_buses(self, **_criteria) -> list[TransportOption]:
        raise ProviderNotConfiguredError(
            "Busbud search is disabled until partner credentials and official API documentation are configured."
        )
