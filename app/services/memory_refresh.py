from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models.brief import ProjectBrief
from app.db.models.memory import ProjectMemory
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.schemas.projects import ProjectEventCreate, ProjectEventType, ProjectStatus
from app.services.memories import ensure_project_memory
from app.services.projects import create_project_event

logger = get_logger(__name__)
ShortItem = Annotated[str, Field(min_length=1, max_length=400)]


class MemoryRefreshProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_state: str = Field(max_length=2_000)
    current_focus: str = Field(max_length=2_000)
    next_steps: list[ShortItem] = Field(max_length=20)
    important_decisions: list[ShortItem] = Field(max_length=20)
    architecture_summary: str = Field(max_length=3_000)
    coding_rules: list[ShortItem] = Field(max_length=20)


class MemoryRefreshGenerator(Protocol):
    async def generate(self, input_text: str) -> MemoryRefreshProposal | dict[str, Any]: ...


class OpenAIMemoryRefreshGenerator:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def generate(self, input_text: str) -> MemoryRefreshProposal:
        response = await self._client.responses.parse(
            model=self._model,
            input=input_text,
            instructions=(
                "Refresh a concise software-project memory after one completed task. "
                "Use only supplied facts. Preserve existing values unless the completed task "
                "provides clear evidence of a durable change. Never change project purpose. "
                "Do not invent decisions, rules, architecture, or future work. Keep lists short."
            ),
            text_format=MemoryRefreshProposal,
            reasoning={"effort": "low"},
            max_output_tokens=2_000,
            store=False,
        )
        if response.output_parsed is None:
            raise ValueError("Memory refresh returned no structured output.")
        return response.output_parsed


def _default_generator() -> OpenAIMemoryRefreshGenerator:
    settings = get_settings()
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise RuntimeError("OpenAI is not configured for memory refresh.")
    return OpenAIMemoryRefreshGenerator(
        AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        ),
        settings.memory_refresh_model,
    )


def _short(value: str | None, limit: int) -> str:
    return " ".join((value or "").split())[:limit]


def _short_list(values: list[str], limit: int = 10) -> list[str]:
    return [item for value in values[:limit] if (item := _short(value, 400))]


def _refresh_input(
    project: Project,
    memory: ProjectMemory,
    task: ProjectTask,
    brief: ProjectBrief | None,
) -> str:
    payload: dict[str, Any] = {
        "project": {
            "id": project.id,
            "name": project.name,
            "purpose": _short(memory.purpose, 1_000),
        },
        "current_memory": {
            "current_state": _short(memory.current_state, 1_500),
            "current_focus": _short(memory.current_focus, 1_500),
            "next_steps": _short_list(memory.next_steps),
            "important_decisions": _short_list(memory.important_decisions),
            "architecture_summary": _short(memory.architecture_summary, 2_000),
            "coding_rules": _short_list(memory.coding_rules),
        },
        "completed_task": {
            "title": _short(task.title, 240),
            "description": _short(task.description, 1_500),
            "result_summary": _short(task.result_summary, 2_000),
        },
    }
    if brief is not None:
        payload["relevant_brief"] = {
            "title": _short(brief.title, 240),
            "summary": _short(brief.summary, 1_000),
            "decisions": _short_list(brief.decisions, 8),
        }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


async def _relevant_brief(
    session: AsyncSession, project_id: str, task_id: str
) -> ProjectBrief | None:
    return await session.scalar(
        select(ProjectBrief)
        .where(
            ProjectBrief.project_id == project_id,
            or_(
                ProjectBrief.task_id == task_id,
                ProjectBrief.status.in_(("READY", "BUILDING")),
            ),
        )
        .order_by(
            case((ProjectBrief.task_id == task_id, 0), else_=1), ProjectBrief.updated_at.desc()
        )
        .limit(1)
    )


def _apply_proposal(memory: ProjectMemory, proposal: MemoryRefreshProposal) -> bool:
    changed = False
    for field, value in proposal.model_dump().items():
        if getattr(memory, field) != value:
            setattr(memory, field, value)
            changed = True
    return changed


async def refresh_project_memory_after_task(
    session: AsyncSession,
    project_id: str,
    task_id: str,
    generator: MemoryRefreshGenerator | None = None,
) -> bool:
    """Refresh concise memory once for an explicitly meaningful successful task."""
    task = await session.get(ProjectTask, task_id)
    if task is None or task.project_id != project_id:
        raise AppError("TASK_NOT_FOUND", "Task not found for this project.", 404)
    if (
        task.status != "DONE"
        or not task.updates_memory
        or not (task.result_summary or "").strip()
        or task.memory_refresh_attempted_at is not None
    ):
        return False

    task.memory_refresh_attempted_at = datetime.now(UTC)
    await session.commit()

    try:
        project = await session.get(Project, project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
        memory = await ensure_project_memory(session, project_id)
        brief = await _relevant_brief(session, project_id, task_id)
        refresh_generator = generator or _default_generator()
        proposal = MemoryRefreshProposal.model_validate(
            await refresh_generator.generate(_refresh_input(project, memory, task, brief))
        )
    except Exception as error:
        logger.warning(
            "project_memory_refresh_failed",
            extra={
                "project_id": project_id,
                "task_id": task_id,
                "error_type": type(error).__name__,
            },
        )
        return False

    changed = _apply_proposal(memory, proposal)
    completed_at = datetime.now(UTC)
    task.memory_refresh_completed_at = completed_at
    if not changed:
        await session.commit()
        return False

    memory.updated_at = completed_at
    await create_project_event(
        session,
        project_id,
        ProjectEventCreate(
            task_id=task.id,
            type=ProjectEventType.MEMORY_UPDATED,
            status=ProjectStatus.DONE,
            message="Project memory refreshed after completed task.",
            agent=task.agent,
        ),
        task,
    )
    return True
