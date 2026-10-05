import json

from langchain_core.messages import ToolMessage

from app.tools import get_tool
from app.utils.retry import retry


class ToolExecutor:

    def _invoke_tool(self, tool, tool_args):
        @retry(max_attempts=3, delay_seconds=1.0)
        def invoke():
            return tool.invoke(tool_args)

        return invoke()

    def execute(self, tool_call) -> ToolMessage:
        tool_name = tool_call["name"]
        tool_call_id = tool_call["id"]
        tool_args = tool_call["args"]

        try:
            tool = get_tool(tool_name)

            result = self._invoke_tool(
                tool,
                tool_args,
            )

            # -------------------------------------------------
            # Serialize structured tool results
            # -------------------------------------------------
            if isinstance(result, list):
                content = json.dumps(
                    [
                        item.model_dump()
                        if hasattr(item, "model_dump")
                        else item
                        for item in result
                    ]
                )
            elif hasattr(result, "model_dump"):
                content = json.dumps(
                    result.model_dump()
                )
            else:
                content = str(result)

            return ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
            )

        except Exception as exc:

            return ToolMessage(
                content=(
                    f"TOOL_ERROR: "
                    f"{tool_name} failed. "
                    f"Error: {exc}"
                ),
                tool_call_id=tool_call_id,
            )