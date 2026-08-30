from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.brief import ProjectBrief
from app.db.models.memory import ProjectMemory
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.schemas.projects import (
    ProjectContext,
    ProjectMemoryRead,
    ProjectMemoryUpdate,
)
from app.services.briefs import brief_to_schema


async def _project(session: AsyncSession, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
    return project


def memory_to_schema(memory: ProjectMemory) -> ProjectMemoryRead:
    return ProjectMemoryRead(
        id=memory.id,
        project_id=memory.project_id,
        purpose=memory.purpose,
        current_state=memory.current_state,
        architecture_summary=memory.architecture_summary,
        important_decisions=memory.important_decisions,
        coding_rules=memory.coding_rules,
        current_focus=memory.current_focus,
        next_steps=memory.next_steps,
        updated_at=memory.updated_at,
    )


def apply_memory_update(
    memory: ProjectMemory, payload: ProjectMemoryUpdate, timestamp: datetime
) -> None:
    for field, value in payload.model_dump().items():
        setattr(memory, field, value)
    memory.updated_at = timestamp


async def ensure_project_memory(session: AsyncSession, project_id: str) -> ProjectMemory:
    await _project(session, project_id)
    await session.execute(
        insert(ProjectMemory)
        .values(
            id=str(uuid4()),
            project_id=project_id,
            purpose="",
            current_state="",
            architecture_summary="",
            important_decisions=[],
            coding_rules=[],
            current_focus="",
            next_steps=[],
        )
        .on_conflict_do_nothing(index_elements=[ProjectMemory.project_id])
    )
    await session.commit()
    memory = await session.scalar(
        select(ProjectMemory).where(ProjectMemory.project_id == project_id)
    )
    if memory is None:  # Defensive: the unique insert/select must produce one row.
        raise AppError("MEMORY_NOT_FOUND", "Project memory could not be loaded.", 500)
    return memory


async def get_memory(session: AsyncSession, project_id: str) -> ProjectMemoryRead:
    return memory_to_schema(await ensure_project_memory(session, project_id))


async def update_memory(
    session: AsyncSession, project_id: str, payload: ProjectMemoryUpdate
) -> ProjectMemoryRead:
    memory = await ensure_project_memory(session, project_id)
    apply_memory_update(memory, payload, datetime.now(UTC))
    await session.commit()
    return memory_to_schema(memory)


async def get_project_context(session: AsyncSession, project_id: str) -> ProjectContext:
    from app.services.projects import task_to_schema

    project = await _project(session, project_id)
    memory = await ensure_project_memory(session, project_id)
    active_brief = await session.scalar(
        select(ProjectBrief)
        .where(
            ProjectBrief.project_id == project_id,
            ProjectBrief.status.in_(("READY", "BUILDING")),
        )
        .order_by(ProjectBrief.updated_at.desc())
        .limit(1)
    )
    current_task = await session.scalar(
        select(ProjectTask)
        .where(ProjectTask.project_id == project_id, ProjectTask.status == "RUNNING")
        .order_by(ProjectTask.updated_at.desc())
        .limit(1)
    )
    return ProjectContext(
        project_id=project.id,
        project_name=project.name,
        memory=memory_to_schema(memory),
        active_brief=brief_to_schema(active_brief) if active_brief else None,
        current_task=task_to_schema(current_task) if current_task else None,
    )
