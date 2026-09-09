from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


class ToolRegistry:
    """Registry for business tools callable by the voice agent."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tools formatted for LLM function calling schema."""
        tools_schema = []
        for tool in self._tools.values():
            tools_schema.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return tools_schema

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute tool by name, handling both sync and async handlers."""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Tool '{name}' not found."}

        try:
            import inspect

            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**arguments)
            else:
                result = tool.handler(**arguments)
            return {"status": "success", "result": result}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc)}
