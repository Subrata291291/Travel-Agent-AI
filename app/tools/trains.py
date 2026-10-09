from typing import List

from langchain_core.tools import tool

from app.providers.errors import ProviderNotConfiguredError
from app.schemas.transport import TransportOption


@tool
def search_trains(origin: str, destination: str, departure_date: str,
                  travellers: int = 1) -> List[TransportOption]:
    """Search trains through an authorized IRCTC Principal Service Provider.

    Search is unavailable until an authorized provider, its official API
    documentation, and credentials are supplied.
    """
    raise ProviderNotConfiguredError(
        "Train search is disabled until an authorized IRCTC Principal Service Provider integration is documented and configured."
    )
