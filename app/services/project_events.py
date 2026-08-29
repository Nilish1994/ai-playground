import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.schemas.projects import ProjectEventEnvelope


class ProjectEventBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[ProjectEventEnvelope]] = set()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[ProjectEventEnvelope]]:
        queue: asyncio.Queue[ProjectEventEnvelope] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, event: ProjectEventEnvelope) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)


project_event_broker = ProjectEventBroker()
