from langchain_core.messages import ToolMessage

from app.llm.router import LLMRouter
from app.tools.weather import get_weather


def main():

    router = LLMRouter()

    llm = router.get_primary_llm()

    tools = [
        get_weather
    ]

    llm_with_tools = llm.bind_tools(
        tools
    )

    # --------------------------------
    # Step 1: User message
    # --------------------------------

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

    # --------------------------------
    # Step 2: Ask LLM
    # --------------------------------

    response = llm_with_tools.invoke(
        messages
    )

    messages.append(response)

    print("\n==============================")
    print("STEP 1 - LLM TOOL CALL")
    print("==============================\n")

    print(response.tool_calls)

    # --------------------------------
    # Step 3: Execute tools
    # --------------------------------

    for tool_call in response.tool_calls:

        if tool_call["name"] == "get_weather":

            result = get_weather.invoke(
                tool_call["args"]
            )

            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )

            messages.append(
                tool_message
            )

            print("\n==============================")
            print("STEP 2 - TOOL RESULT")
            print("==============================\n")

            print(result)

    # --------------------------------
    # Step 4: Give result back to LLM
    # --------------------------------

    final_response = llm_with_tools.invoke(
        messages
    )

    print("\n==============================")
    print("STEP 3 - FINAL ANSWER")
    print("==============================\n")

    print(
        final_response.content
    )


if __name__ == "__main__":
    main()