from app.llm.router import LLMRouter
from app.tools import get_all_tools
from app.agents.executor import ToolExecutor


def main():

    router = LLMRouter()

    llm = router.get_primary_llm()

    tools = get_all_tools()

    llm_with_tools = llm.bind_tools(
        tools
    )

    messages = [
    (
        "system",
        """
        You are a helpful travel assistant.

        Use available tools whenever necessary.

        When the user asks for bus options,
        use the search_buses tool.
        """
    ),
    (
        "human",
        "Find bus options from Kolkata to Manali for December 20, 2026 for 2 travellers."
    ),
]

    # -------------------------
    # LLM decides tool
    # -------------------------

    response = llm_with_tools.invoke(
        messages
    )

    print("\n==============================")
    print("TOOL CALL")
    print("==============================\n")

    print(
        response.tool_calls
    )

    # -------------------------
    # Execute tool
    # -------------------------

    executor = ToolExecutor()

    for tool_call in response.tool_calls:

        tool_message = executor.execute(
            tool_call
        )

        print("\n==============================")
        print("EXECUTED TOOL")
        print("==============================\n")

        print(
            tool_message.content
        )


if __name__ == "__main__":
    main()