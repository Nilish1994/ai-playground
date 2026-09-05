import asyncio

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import DbSessionDep, SettingsDep
from app.core.errors import AppError
from app.schemas.projects import (
    ProjectDiscoveryResult,
    ProjectEventCreate,
    ProjectEventEnvelope,
    ProjectOnboardingResult,
    ProjectRead,
)
from app.services.project_discovery import discover_projects, onboard_project
from app.services.project_events import project_event_broker
from app.services.projects import create_project_event, get_project, list_projects

router = APIRouter(prefix="/projects", tags=["projects"])
events_router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[ProjectRead])
async def projects(session: DbSessionDep) -> list[ProjectRead]:
    return await list_projects(session)


@router.post("/discover", response_model=ProjectDiscoveryResult)
async def discover(session: DbSessionDep, settings: SettingsDep) -> ProjectDiscoveryResult:
    return await discover_projects(session, settings.projects_root)


@router.post("/{project_id}/onboard", response_model=ProjectOnboardingResult)
async def onboard(
    project_id: str, session: DbSessionDep, settings: SettingsDep
) -> ProjectOnboardingResult:
    return await onboard_project(session, project_id, settings.projects_root)


@router.get("/{project_id}", response_model=ProjectRead)
async def project(project_id: str, session: DbSessionDep) -> ProjectRead:
    return await get_project(session, project_id)


@router.post(
    "/{project_id}/events",
    response_model=ProjectEventEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    project_id: str,
    payload: ProjectEventCreate,
    session: DbSessionDep,
    settings: SettingsDep,
) -> ProjectEventEnvelope:
    if settings.app_env.lower() == "production":
        raise AppError("DEVELOPMENT_ENDPOINT_DISABLED", "Endpoint is disabled.", 404)
    return await create_project_event(session, project_id, payload)


@events_router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    async def event_stream():
        yield ": connected\n\n"
        async with project_event_broker.subscribe() as queue:
            while not await request.is_disconnected():
                try:
                    envelope = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: project_event\ndata: {envelope.model_dump_json()}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
