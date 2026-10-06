from app.tools.trains import search_trains
from app.tools.weather import get_weather
from app.tools.flights import search_flights
from app.tools.buses import search_buses
from app.tools.hotels import search_hotels

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "search_trains": search_trains,
    "search_flights": search_flights,
    "search_buses": search_buses,
    "search_hotels": search_hotels,
}


def get_tool(
    tool_name: str
):

    if tool_name not in TOOL_REGISTRY:
        raise ValueError(
            f"Unknown tool: {tool_name}"
        )

    return TOOL_REGISTRY[tool_name]


def get_all_tools():
    return list(
        TOOL_REGISTRY.values()
    )