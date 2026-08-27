from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_chat_service
from app.main import app
from app.services.chat import ChatResult


@dataclass
class FakeChatService:
    async def reply(self, prompt: str) -> ChatResult:
        return ChatResult(text=f"Reply to: {prompt}", model="test-model", response_id="resp_test")


@pytest.fixture(autouse=True)
def override_chat_service() -> None:
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat", json={"prompt": "Hello"})

    assert response.status_code == 200
    assert response.json() == {
        "response": "Reply to: Hello",
        "model": "test-model",
        "response_id": "resp_test",
    }


@pytest.mark.asyncio
async def test_chat_rejects_blank_prompt(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat", json={"prompt": "   "})

    assert response.status_code == 422
