from fastapi import APIRouter, BackgroundTasks, status

from app.api.dependencies import DbSessionDep
from app.schemas.projects import (
    ProjectEventCreate,
    ProjectEventEnvelope,
    ProjectEventRead,
    ProjectTaskCreate,
    ProjectTaskDetail,
    ProjectTaskRead,
    TaskAction,
    TaskExecutionAccepted,
)
from app.services.codex_executor import codex_executor
from app.services.tasks import (
    complete_task,
    create_task,
    create_task_event,
    fail_task,
    get_task,
    list_tasks,
    start_task,
    task_events,
)

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["project tasks"])


@router.get("", response_model=list[ProjectTaskRead])
async def tasks(project_id: str, session: DbSessionDep) -> list[ProjectTaskRead]:
    return await list_tasks(session, project_id)


@router.post("", response_model=ProjectTaskRead, status_code=status.HTTP_201_CREATED)
async def new_task(
    project_id: str, payload: ProjectTaskCreate, session: DbSessionDep
) -> ProjectTaskRead:
    return await create_task(session, project_id, payload)


@router.get("/{task_id}", response_model=ProjectTaskDetail)
async def task(project_id: str, task_id: str, session: DbSessionDep) -> ProjectTaskDetail:
    return await get_task(session, project_id, task_id)


@router.post(
    "/{task_id}/execute",
    response_model=TaskExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute(
    project_id: str,
    task_id: str,
    background_tasks: BackgroundTasks,
    session: DbSessionDep,
) -> TaskExecutionAccepted:
    request = await codex_executor.reserve(session, project_id, task_id)
    background_tasks.add_task(codex_executor.execute, request)
    return TaskExecutionAccepted(project_id=project_id, task_id=task_id)


@router.post("/{task_id}/start", response_model=ProjectTaskRead)
async def start(
    project_id: str, task_id: str, action: TaskAction, session: DbSessionDep
) -> ProjectTaskRead:
    return await start_task(session, project_id, task_id, action)


@router.post("/{task_id}/complete", response_model=ProjectTaskRead)
async def complete(
    project_id: str, task_id: str, action: TaskAction, session: DbSessionDep
) -> ProjectTaskRead:
    return await complete_task(session, project_id, task_id, action)


@router.post("/{task_id}/fail", response_model=ProjectTaskRead)
async def fail(
    project_id: str, task_id: str, action: TaskAction, session: DbSessionDep
) -> ProjectTaskRead:
    return await fail_task(session, project_id, task_id, action)


@router.get("/{task_id}/events", response_model=list[ProjectEventRead])
async def events(project_id: str, task_id: str, session: DbSessionDep) -> list[ProjectEventRead]:
    return await task_events(session, project_id, task_id)


@router.post(
    "/{task_id}/events",
    response_model=ProjectEventEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def new_event(
    project_id: str,
    task_id: str,
    payload: ProjectEventCreate,
    session: DbSessionDep,
) -> ProjectEventEnvelope:
    return await create_task_event(session, project_id, task_id, payload)
