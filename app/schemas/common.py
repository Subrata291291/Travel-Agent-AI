from typing import Optional

from pydantic import BaseModel


class ResolvedDestination(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: Optional[str] = None
    country_code: Optional[str] = None
    admin1: Optional[str] = None
    admin2: Optional[str] = None
    timezone: Optional[str] = None