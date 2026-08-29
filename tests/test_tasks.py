from datetime import UTC, datetime

from app.db.models.task import ProjectTask
from app.schemas.projects import ProjectEventCreate, ProjectEventType, ProjectStatus
from app.services.tasks import apply_task_event_transition


def task() -> ProjectTask:
    return ProjectTask(
        id="task-id",
        project_id="project-id",
        title="Test task",
        status="PENDING",
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
