from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.db.models.task import ProjectTask
from app.schemas.projects import ProjectEventCreate, ProjectEventType, ProjectStatus
from app.services import tasks as tasks_module
from app.services.tasks import apply_task_event_transition, complete_task


def task() -> ProjectTask:
    return ProjectTask(
        id="task-id",
        project_id="project-id",
        title="Test task",
        status="PENDING",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def event(event_type: ProjectEventType, status: ProjectStatus, agent: str | None = None):
    return ProjectEventCreate(
        task_id="task-id",
        type=event_type,
        status=status,
        message="Test event",
        agent=agent,
    )


def test_task_lifecycle_transition() -> None:
    item = task()
    timestamp = datetime.now(UTC)

    apply_task_event_transition(
        item, event(ProjectEventType.TASK_STARTED, ProjectStatus.RUNNING, "Codex"), timestamp
    )
    assert item.status == "RUNNING"
    assert item.started_at == timestamp
    assert item.agent == "Codex"

    apply_task_event_transition(
        item, event(ProjectEventType.TASK_COMPLETED, ProjectStatus.DONE), timestamp
    )
    assert item.status == "DONE"
    assert item.completed_at == timestamp


def test_non_lifecycle_event_preserves_task_status() -> None:
    item = task()
    apply_task_event_transition(
        item,
        event(ProjectEventType.FILE_CHANGED, ProjectStatus.RUNNING, "Codex"),
        datetime.now(UTC),
    )
    assert item.status == "PENDING"
    assert item.agent == "Codex"


@pytest.mark.asyncio
async def test_successful_task_stays_done_when_refresh_unexpectedly_fails(monkeypatch) -> None:
    item = task()
    item.status = "RUNNING"
    item.updates_memory = True
    monkeypatch.setattr(tasks_module, "_task", AsyncMock(return_value=item))

    async def complete_event(_session, _project_id, payload, task_item):
        apply_task_event_transition(task_item, payload, datetime.now(UTC))
        return tasks_module.ProjectEventEnvelope.model_construct(
            event=None, project=None, task=tasks_module.task_to_schema(task_item)
        )

    monkeypatch.setattr(tasks_module, "create_project_event", complete_event)
    refresh = AsyncMock(side_effect=RuntimeError("unexpected refresh failure"))
    monkeypatch.setattr(tasks_module, "refresh_project_memory_after_task", refresh)

    session = object()
    result = await complete_task(
        session,
        "project-id",
        "task-id",
        tasks_module.TaskAction(result_summary="Coding work succeeded"),
    )

    assert result.status == "DONE"
    assert result.result_summary == "Coding work succeeded"
    refresh.assert_awaited_once_with(session, "project-id", "task-id")
