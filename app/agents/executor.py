from langchain_core.messages import ToolMessage

from app.tools import get_tool


class ToolExecutor:

    def execute(
        self,
        tool_call,
    ) -> ToolMessage:

        tool_name = tool_call["name"]

        tool = get_tool(
            tool_name
        )

        result = tool.invoke(
            tool_call["args"]
        )

        return ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"],
        )