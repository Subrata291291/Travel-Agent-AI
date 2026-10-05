from langchain_core.tools import tool

from app.agents.executor import ToolExecutor
from app.tools import TOOL_REGISTRY


@tool
def failing_weather(location: str) -> dict:
    """
    Simulates a temporary weather service failure.
    """
    raise TimeoutError(
        "Weather service temporarily unavailable"
    )


TOOL_REGISTRY["failing_weather"] = failing_weather


executor = ToolExecutor()

tool_call = {
    "name": "failing_weather",
    "args": {
        "location": "Manali",
    },
    "id": "test-failure-001",
    "type": "tool_call",
}


print()
print("==============================")
print("GRACEFUL FAILURE TEST")
print("==============================")


result = executor.execute(tool_call)


print()
print("==============================")
print("TOOL MESSAGE")
print("==============================")

print(result.content)