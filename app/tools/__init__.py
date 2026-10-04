from app.tools.weather import get_weather


TOOL_REGISTRY = {
    "get_weather": get_weather,
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