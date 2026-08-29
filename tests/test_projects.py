from datetime import UTC, datetime

from app.db.models.project import Project
from app.schemas.projects import ProjectEventCreate, ProjectEventType, ProjectStatus
from app.services.projects import apply_event_transition


def project() -> Project:
    return Project(
        id="test-project",
        name="Test Project",
        path="/tmp/test-project",
        status="IDLE",
        recent_files=[],
        checks=[],
    )


def event(event_type: ProjectEventType, status: ProjectStatus, **values) -> ProjectEventCreate:
    return ProjectEventCreate(
        type=event_type,
        status=status,
        message=values.pop("message", "Test event"),
        **values,
    )


def test_task_transition_tracks_current_and_completed_task() -> None:
    item = project()
    timestamp = datetime.now(UTC)

    apply_event_transition(
        item,
        event(ProjectEventType.TASK_STARTED, ProjectStatus.RUNNING, message="Build dashboard"),
        timestamp,
    )
    assert item.status == "RUNNING"
    assert item.current_task == "Build dashboard"

    apply_event_transition(
        item,
        event(ProjectEventType.TASK_COMPLETED, ProjectStatus.DONE, message="Dashboard built"),
        timestamp,
    )
    assert item.status == "DONE"
    assert item.current_task is None
    assert item.last_completed_task == "Build dashboard"


def test_file_event_deduplicates_recent_files() -> None:
    item = project()
    item.recent_files = ["old.py", "changed.py"]

    apply_event_transition(
        item,
        event(
            ProjectEventType.FILE_CHANGED,
            ProjectStatus.RUNNING,
            file="changed.py",
        ),
        datetime.now(UTC),
    )

    assert item.recent_files == ["changed.py", "old.py"]


def test_build_and_agent_events_update_project_state() -> None:
    item = project()
    timestamp = datetime.now(UTC)

    apply_event_transition(
        item,
        event(
            ProjectEventType.AGENT_STARTED,
            ProjectStatus.RUNNING,
            agent="Codex",
        ),
        timestamp,
    )
    apply_event_transition(
        item,
        event(
            ProjectEventType.BUILD_PASSED,
            ProjectStatus.DONE,
            message="Frontend build passed",
            agent="Codex",
        ),
        timestamp,
    )

    assert item.active_agent == "Codex"
    assert item.checks == [{"label": "build", "status": "DONE", "detail": "Frontend build passed"}]
