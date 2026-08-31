from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models.project import Project, ProjectEvent
from app.db.models.task import ProjectTask
from app.schemas.projects import (
    ProjectEventCreate,
    ProjectEventEnvelope,
    ProjectEventRead,
    ProjectEventType,
    ProjectStatus,
    ProjectTaskCreate,
    ProjectTaskDetail,
    ProjectTaskRead,
    TaskAction,
)
from app.services.memory_refresh import refresh_project_memory_after_task
from app.services.projects import create_project_event, event_to_schema, task_to_schema

logger = get_logger(__name__)


def apply_task_event_transition(
    task: ProjectTask, event: ProjectEventCreate, timestamp: datetime
) -> None:
    task.updated_at = timestamp
    if event.agent:
        task.agent = event.agent
    if event.type == ProjectEventType.TASK_STARTED:
        task.status = "RUNNING"
        task.started_at = task.started_at or timestamp
    elif event.type == ProjectEventType.TASK_COMPLETED:
        task.status = "DONE"
        task.completed_at = timestamp
    elif event.type == ProjectEventType.TASK_FAILED:
        task.status = "FAILED"
        task.completed_at = timestamp


async def _task(session: AsyncSession, project_id: str, task_id: str) -> ProjectTask:
    task = await session.get(ProjectTask, task_id)
    if task is None or task.project_id != project_id:
        raise AppError("TASK_NOT_FOUND", "Task not found for this project.", 404)
    return task


async def list_tasks(session: AsyncSession, project_id: str) -> list[ProjectTaskRead]:
    if await session.get(Project, project_id) is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
    tasks = (
        await session.scalars(
            select(ProjectTask)
            .where(ProjectTask.project_id == project_id)
            .order_by(ProjectTask.created_at.desc())
        )
    ).all()
    return [task_to_schema(task) for task in tasks]


async def get_task(session: AsyncSession, project_id: str, task_id: str) -> ProjectTaskDetail:
    task = await _task(session, project_id, task_id)
    events = await task_events(session, project_id, task_id)
    return ProjectTaskDetail(**task_to_schema(task).model_dump(), events=events)


async def create_task(
    session: AsyncSession, project_id: str, payload: ProjectTaskCreate
) -> ProjectTaskRead:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
    timestamp = datetime.now(UTC)
    task = ProjectTask(
        id=str(uuid4()),
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        prompt=payload.prompt,
        status="PENDING",
        agent=payload.agent,
        updates_memory=payload.updates_memory,
        created_at=timestamp,
        updated_at=timestamp,
    )
    project.current_task = payload.title
    session.add(task)
    await session.flush()
    await create_project_event(
        session,
        project_id,
        ProjectEventCreate(
            task_id=task.id,
            type=ProjectEventType.TASK_CREATED,
            status=ProjectStatus.IDLE,
            message=f"Task created: {task.title}",
            agent=task.agent,
        ),
        task,
    )
    return task_to_schema(task)


async def start_task(
    session: AsyncSession, project_id: str, task_id: str, action: TaskAction
) -> ProjectTaskRead:
    task = await _task(session, project_id, task_id)
    if task.status != "PENDING":
        raise AppError("INVALID_TASK_STATE", "Only pending tasks can be started.", 409)
    envelope = await create_project_event(
        session,
        project_id,
        ProjectEventCreate(
            task_id=task.id,
            type=ProjectEventType.TASK_STARTED,
            status=ProjectStatus.RUNNING,
            message=action.message or task.title,
            agent=action.agent or task.agent,
        ),
        task,
    )
    return envelope.task


async def complete_task(
    session: AsyncSession, project_id: str, task_id: str, action: TaskAction
) -> ProjectTaskRead:
    task = await _task(session, project_id, task_id)
    if task.status != "RUNNING":
        raise AppError("INVALID_TASK_STATE", "Only running tasks can be completed.", 409)
    task.result_summary = action.result_summary or action.message
    envelope = await create_project_event(
        session,
        project_id,
        ProjectEventCreate(
            task_id=task.id,
            type=ProjectEventType.TASK_COMPLETED,
            status=ProjectStatus.DONE,
            message=action.message or f"Task completed: {task.title}",
            agent=action.agent or task.agent,
        ),
        task,
    )
    try:
        await refresh_project_memory_after_task(session, project_id, task_id)
    except Exception as error:
        logger.warning(
            "project_memory_refresh_unexpected_failure",
            extra={
                "project_id": project_id,
                "task_id": task_id,
                "error_type": type(error).__name__,
            },
        )
    return envelope.task


async def fail_task(
    session: AsyncSession, project_id: str, task_id: str, action: TaskAction
) -> ProjectTaskRead:
    task = await _task(session, project_id, task_id)
    if task.status not in {"PENDING", "RUNNING"}:
        raise AppError("INVALID_TASK_STATE", "Only active tasks can be failed.", 409)
    task.result_summary = action.result_summary or action.message
    envelope = await create_project_event(
        session,
        project_id,
        ProjectEventCreate(
            task_id=task.id,
            type=ProjectEventType.TASK_FAILED,
            status=ProjectStatus.FAILED,
            message=action.message or f"Task failed: {task.title}",
            agent=action.agent or task.agent,
        ),
        task,
    )
    return envelope.task


async def task_events(
    session: AsyncSession, project_id: str, task_id: str
) -> list[ProjectEventRead]:
    await _task(session, project_id, task_id)
    events = (
        await session.scalars(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == project_id, ProjectEvent.task_id == task_id)
            .order_by(ProjectEvent.timestamp.asc())
        )
    ).all()
    return [event_to_schema(event) for event in events]


async def create_task_event(
    session: AsyncSession,
    project_id: str,
    task_id: str,
    payload: ProjectEventCreate,
) -> ProjectEventEnvelope:
    task = await _task(session, project_id, task_id)
    return await create_project_event(
        session,
        project_id,
        payload.model_copy(update={"task_id": task_id}),
        task,
    )
