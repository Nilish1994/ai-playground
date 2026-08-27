from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.errors import AppError
from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ChatResult:
    text: str
    model: str
    response_id: str


class ChatService:
    def __init__(self, client: AsyncOpenAI, model: str, tools: ToolRegistry) -> None:
        self._client = client
        self._model = model
        self._tools = tools

    async def reply(self, prompt: str) -> ChatResult:
        logger.info("chat_request_started", extra={"model": self._model})
        response = await self._client.responses.create(
            model=self._model,
            input=prompt,
            tools=self._tools.openai_definitions(),
            store=False,
        )
        if not response.output_text:
            raise AppError("EMPTY_AI_RESPONSE", "The AI service returned no text.", 502)
        logger.info("chat_request_completed", extra={"model": response.model})
        return ChatResult(text=response.output_text, model=response.model, response_id=response.id)
