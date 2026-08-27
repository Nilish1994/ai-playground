from typing import Any

from app.tools.base import AssistantTool


class ToolRegistry:
    def __init__(self, tools: tuple[AssistantTool, ...] = ()) -> None:
        self._tools = {tool.definition["name"]: tool for tool in tools}

    def openai_definitions(self) -> list[dict[str, Any]]:
        return [tool.definition for tool in self._tools.values()]

    def get(self, name: str) -> AssistantTool:
        return self._tools[name]
