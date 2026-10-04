from app.llm.router import LLMRouter
from app.tools.weather import get_weather


def main():

    router = LLMRouter()

    llm = router.get_primary_llm()

    llm_with_tools = llm.bind_tools(
        [get_weather]
    )

    messages = [
        (
            "system",
            """
            You are a helpful travel assistant.

            Use the weather tool whenever the user
            asks for current weather information.
            """
        ),
        (
            "human",
            "What is the current weather in Manali?"
        ),
    ]

    response = llm_with_tools.invoke(
        messages
    )

    print("\n==============================")
    print("LLM RESPONSE")
    print("==============================\n")

    print(response)

    print("\n==============================")
    print("TOOL CALLS")
    print("==============================\n")

    print(
        response.tool_calls
    )


if __name__ == "__main__":
    main()