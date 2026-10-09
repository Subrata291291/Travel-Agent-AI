"""Search contract for an IRCTC-authorized Principal Service Provider."""

from typing import Protocol

from app.schemas.transport import TransportOption


class AuthorizedRailProvider(Protocol):
    def search_trains(self, origin: str, destination: str, departure_date: str,
                      travellers: int = 1) -> list[TransportOption]: ...
