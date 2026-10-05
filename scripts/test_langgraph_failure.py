from langchain_core.tools import tool

from app.tools import TOOL_REGISTRY


@tool
def failing_weather(
    location: str,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    country: str | None = None,
    admin1: str | None = None,
    resolved_destination: dict | None = None,
) -> dict:
    """
    Simulates a temporary weather service failure.
    """
    raise TimeoutError(
        "Weather service temporarily unavailable"
    )


# Temporarily replace the production weather tool
# for this isolated test.
TOOL_REGISTRY["get_weather"] = failing_weather


from app.agents.graph import TravelAgentGraph


print()
print("==============================")
print("LANGGRAPH GRACEFUL FAILURE TEST")
print("==============================")


agent = TravelAgentGraph()


result = agent.run(
    user_message=(
        "What is the current weather in "
        "Manali, Himachal Pradesh?"
    ),
    user_id="test-user",
    session_id="failure-test-session",
)


print()
print("==============================")
print("FINAL ANSWER")
print("==============================")

print(result["answer"])