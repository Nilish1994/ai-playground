from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db_session
from app.services.chat import ChatService
from app.tools.registry import ToolRegistry

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry()


def get_openai_client(settings: SettingsDep) -> AsyncOpenAI:
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise AppError("OPENAI_NOT_CONFIGURED", "The AI service is not configured.", 503)
    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )


def get_chat_service(
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
    settings: SettingsDep,
    tools: Annotated[ToolRegistry, Depends(get_tool_registry)],
) -> ChatService:
    return ChatService(client=client, model=settings.openai_model, tools=tools)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
