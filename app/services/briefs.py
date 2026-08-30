from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.brief import ProjectBrief
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.schemas.projects import (
    BriefTaskLink,
    ProjectBriefCreate,
    ProjectBriefRead,
    ProjectBriefUpdate,
)


async def _project(session: AsyncSession, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
    return project


async def _brief(session: AsyncSession, project_id: str, brief_id: str) -> ProjectBrief:
    brief = await session.get(ProjectBrief, brief_id)
    if brief is None or brief.project_id != project_id:
        raise AppError("BRIEF_NOT_FOUND", "Brief not found for this project.", 404)
    return brief


async def _validate_task(session: AsyncSession, project_id: str, task_id: str) -> None:
    task = await session.get(ProjectTask, task_id)
    if task is None or task.project_id != project_id:
        raise AppError("TASK_NOT_FOUND", "Task not found for this project.", 404)


def brief_to_schema(brief: ProjectBrief) -> ProjectBriefRead:
    return ProjectBriefRead(
        id=brief.id,
        project_id=brief.project_id,
        title=brief.title,
        summary=brief.summary,
        decisions=brief.decisions,
        build_prompt=brief.build_prompt,
        status=brief.status,
        task_id=brief.task_id,
        created_at=brief.created_at,
        updated_at=brief.updated_at,
    )


def apply_brief_updates(
    brief: ProjectBrief, payload: ProjectBriefUpdate, timestamp: datetime
) -> None:
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    for field, value in changes.items():
        setattr(brief, field, value)
    brief.updated_at = timestamp


async def list_briefs(session: AsyncSession, project_id: str) -> list[ProjectBriefRead]:
    await _project(session, project_id)
    briefs = (
        await session.scalars(
            select(ProjectBrief)
            .where(ProjectBrief.project_id == project_id)
            .order_by(ProjectBrief.updated_at.desc())
        )
    ).all()
    return [brief_to_schema(brief) for brief in briefs]


async def get_brief(session: AsyncSession, project_id: str, brief_id: str) -> ProjectBriefRead:
    return brief_to_schema(await _brief(session, project_id, brief_id))


async def create_brief(
    session: AsyncSession, project_id: str, payload: ProjectBriefCreate
) -> ProjectBriefRead:
    await _project(session, project_id)
    if payload.task_id:
        await _validate_task(session, project_id, payload.task_id)
    timestamp = datetime.now(UTC)
    brief = ProjectBrief(
        id=str(uuid4()),
        project_id=project_id,
        title=payload.title,
        summary=payload.summary,
        decisions=payload.decisions,
        build_prompt=payload.build_prompt,
        status=payload.status.value,
        task_id=payload.task_id,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(brief)
    await session.commit()
    return brief_to_schema(brief)


async def update_brief(
    session: AsyncSession,
    project_id: str,
    brief_id: str,
    payload: ProjectBriefUpdate,
) -> ProjectBriefRead:
    brief = await _brief(session, project_id, brief_id)
    changes = payload.model_dump(exclude_unset=True)
    if "task_id" in changes and changes["task_id"]:
        await _validate_task(session, project_id, changes["task_id"])
    apply_brief_updates(brief, payload, datetime.now(UTC))
    await session.commit()
    return brief_to_schema(brief)


async def link_brief_task(
    session: AsyncSession,
    project_id: str,
    brief_id: str,
    payload: BriefTaskLink,
) -> ProjectBriefRead:
    brief = await _brief(session, project_id, brief_id)
    if payload.task_id:
        await _validate_task(session, project_id, payload.task_id)
    brief.task_id = payload.task_id
    brief.updated_at = datetime.now(UTC)
    await session.commit()
    return brief_to_schema(brief)
