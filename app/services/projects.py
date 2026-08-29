from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.brief import ProjectBrief
from app.db.models.project import Project, ProjectEvent
from app.db.models.task import ProjectTask
from app.schemas.projects import (
    ProjectCheck,
    ProjectEventCreate,
    ProjectEventEnvelope,
    ProjectEventRead,
    ProjectEventType,
    ProjectRead,
    ProjectTaskRead,
)
from app.services.briefs import brief_to_schema
from app.services.project_events import project_event_broker

SEED_PROJECTS = (
    {"id": "ai-playground", "name": "AI Playground", "path": "/srv/projects/ai-playground"},
    {"id": "office-project", "name": "Office Project", "path": "/srv/projects/project-two-web"},
)


def apply_event_transition(
    project: Project, event: ProjectEventCreate, timestamp: datetime
) -> None:
    project.status = event.status.value
    project.updated_at = timestamp

    if event.type == ProjectEventType.TASK_STARTED:
        project.current_task = event.message
    elif event.type == ProjectEventType.TASK_COMPLETED:
        project.last_completed_task = project.current_task or event.message
        project.current_task = None
    elif event.type == ProjectEventType.TASK_FAILED:
        project.current_task = event.message

    if event.type == ProjectEventType.AGENT_STARTED:
        project.active_agent = event.agent
    elif event.type in {
        ProjectEventType.AGENT_FINISHED,
        ProjectEventType.TASK_COMPLETED,
        ProjectEventType.TASK_FAILED,
    }:
        project.active_agent = None
    elif event.agent and event.type != ProjectEventType.TASK_CREATED:
        project.active_agent = event.agent

    if (
        event.type
        in {
            ProjectEventType.FILE_CREATED,
            ProjectEventType.FILE_CHANGED,
            ProjectEventType.FILE_DELETED,
        }
        and event.file
    ):
        project.recent_files = [
            event.file,
            *(file for file in project.recent_files if file != event.file),
        ][:10]

    check_kind = _check_kind(event.type)
    if check_kind:
        check = {"label": check_kind, "status": event.status.value, "detail": event.message}
        project.checks = [
            check,
            *(existing for existing in project.checks if existing.get("label") != check_kind),
        ]


def _check_kind(event_type: ProjectEventType) -> str | None:
    if event_type.value.startswith("build_"):
        return "build"
    if event_type.value.startswith("test_"):
        return "test suite"
    return None


async def seed_projects(session: AsyncSession) -> None:
    existing = set((await session.scalars(select(Project.id))).all())
    for project in SEED_PROJECTS:
        if project["id"] not in existing:
            session.add(Project(**project, status="IDLE", recent_files=[], checks=[]))
    await session.commit()


async def list_projects(session: AsyncSession) -> list[ProjectRead]:
    projects = (await session.scalars(select(Project).order_by(Project.name))).all()
    return [await build_project_read(session, project) for project in projects]


async def get_project(session: AsyncSession, project_id: str) -> ProjectRead:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
    return await build_project_read(session, project)


async def create_project_event(
    session: AsyncSession,
    project_id: str,
    payload: ProjectEventCreate,
    task: ProjectTask | None = None,
) -> ProjectEventEnvelope:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)

    if payload.task_id:
        task = task or await session.get(ProjectTask, payload.task_id)
        if task is None or task.project_id != project_id:
            raise AppError("TASK_NOT_FOUND", "Task not found for this project.", 404)

    timestamp = datetime.now(UTC)
    event = ProjectEvent(
        event_id=str(uuid4()),
        project_id=project_id,
        task_id=task.id if task else None,
        timestamp=timestamp,
        status=payload.status.value,
        type=payload.type.value,
        message=payload.message,
        agent=payload.agent,
        file=payload.file,
        event_metadata=payload.metadata,
    )
    apply_event_transition(project, payload, timestamp)
    if task:
        from app.services.tasks import apply_task_event_transition

        apply_task_event_transition(task, payload, timestamp)
    session.add(event)
    await session.commit()

    envelope = ProjectEventEnvelope(
        event=event_to_schema(event),
        project=await build_project_read(session, project),
        task=task_to_schema(task) if task else None,
    )
    project_event_broker.publish(envelope)
    return envelope


async def build_project_read(session: AsyncSession, project: Project) -> ProjectRead:
    events = (
        await session.scalars(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == project.id)
            .order_by(ProjectEvent.timestamp.desc())
            .limit(100)
        )
    ).all()
    tasks = (
        await session.scalars(
            select(ProjectTask)
            .where(ProjectTask.project_id == project.id)
            .order_by(ProjectTask.created_at.desc())
        )
    ).all()
    briefs = (
        await session.scalars(
            select(ProjectBrief)
            .where(ProjectBrief.project_id == project.id)
            .order_by(ProjectBrief.updated_at.desc())
        )
    ).all()
    return ProjectRead(
        id=project.id,
        name=project.name,
        path=project.path,
        status=project.status,
        current_task=project.current_task,
        last_completed_task=project.last_completed_task,
        active_agent=project.active_agent,
        updated_at=project.updated_at,
        recent_files=project.recent_files,
        checks=[ProjectCheck.model_validate(check) for check in project.checks],
        tasks=[task_to_schema(task) for task in tasks],
        briefs=[brief_to_schema(brief) for brief in briefs],
        recent_events=[event_to_schema(event) for event in events],
    )



def task_to_schema(task: ProjectTask) -> ProjectTaskRead:
    return ProjectTaskRead(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        prompt=task.prompt,
        status=task.status,
        agent=task.agent,
        result_summary=task.result_summary,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        updated_at=task.updated_at,
    )


def event_to_schema(event: ProjectEvent) -> ProjectEventRead:
    return ProjectEventRead(
        event_id=event.event_id,
        project_id=event.project_id,
        task_id=event.task_id,
        timestamp=event.timestamp,
        status=event.status,
        type=event.type,
        message=event.message,
        agent=event.agent,
        file=event.file,
        metadata=event.event_metadata,
    )
