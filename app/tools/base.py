from typing import Any, Protocol


class AssistantTool(Protocol):
    @property
    def definition(self) -> dict[str, Any]: ...

    async def execute(self, arguments: dict[str, Any]) -> Any: ...
