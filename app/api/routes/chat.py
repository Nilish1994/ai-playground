from fastapi import APIRouter, status

from app.api.dependencies import ChatServiceDep, SettingsDep
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest, service: ChatServiceDep, settings: SettingsDep
) -> ChatResponse:
    if len(request.prompt) > settings.chat_max_prompt_length:
        from app.core.errors import AppError

        raise AppError("PROMPT_TOO_LONG", "The prompt exceeds the configured limit.", 422)
    result = await service.reply(request.prompt)
    return ChatResponse(response=result.text, model=result.model, response_id=result.response_id)
