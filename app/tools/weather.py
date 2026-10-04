import requests

from app.tools.geocoding import GeocodingTool
from langchain_core.tools import tool

class WeatherTool:
    """
    Fetches current weather for a location.

    Flow:
        Location name
            ↓
        Geocoding
            ↓
        Latitude / Longitude
            ↓
        Open-Meteo Weather API
    """

    BASE_URL = (
        "https://api.open-meteo.com/v1/forecast"
    )

    def __init__(self):

        self.geocoding = GeocodingTool()

    def get_weather(
        self,
        location: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        timezone: str | None = None,
        country: str | None = None,
        admin1: str | None = None,
    ) -> dict:

        # -------------------------
        # Step 1: Resolve location
        # -------------------------

        if latitude is None or longitude is None:

            if not location:
                raise ValueError(
                    "Either location or coordinates must be provided."
                )

            place = self.geocoding.search(
                location
            )

            latitude = place["latitude"]
            longitude = place["longitude"]
            location_name = place["name"]
            country_name = place["country"]
            admin1_name = place["admin1"]
            location_timezone = place["timezone"]

        else:

            location_name = location
            country_name = country
            admin1_name = admin1
            location_timezone = timezone

        # -------------------------
        # Step 2: Weather API
        # -------------------------

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "apparent_temperature,"
                "weather_code,"
                "wind_speed_10m"
            ),
            "wind_speed_unit": "kmh",
            "timezone": "auto",
        }

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        # -------------------------
        # Step 3: Return structured
        # result
        # -------------------------

        return {
            "location": {
                "name": location_name,
                "country": country_name,
                "admin1": admin1_name,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": location_timezone,
            },
            "current": data["current"],
        }

weather_service = WeatherTool()


@tool
def get_weather(
    location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    country: str | None = None,
    admin1: str | None = None,
) -> dict:
    """
    Get current weather for a travel destination.

    When canonical coordinates are available from the
    destination resolver, use those coordinates instead
    of resolving the location name again.
    """

    return weather_service.get_weather(
        location=location,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        country=country,
        admin1=admin1,
    )