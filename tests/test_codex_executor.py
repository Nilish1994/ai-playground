from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.core.errors import AppError
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.schemas.projects import ProjectEventType
from app.services import codex_executor as executor_module
from app.services.codex_executor import (
    CodexExecutor,
    ExecutionRequest,
    WorktreeEntry,
    agent_reported_failure,
    command_event_type,
    detect_file_changes,
    parse_porcelain,
    validate_project_path,
)


class FakeSession:
    def __init__(self, project: Project, task: ProjectTask) -> None:
        self.project = project
        self.task = task

    async def get(self, model, key):
        if model is Project and key == self.project.id:
            return self.project
        if model is ProjectTask and key == self.task.id:
            return self.task
        return None


def project(path: Path) -> Project:
    return Project(
        id="project-id",
        name="Project",
        path=str(path),
        status="IDLE",
        recent_files=[],
        checks=[],
    )


def task(prompt: str | None = "Build it") -> ProjectTask:
    return ProjectTask(
        id="task-id",
        project_id="project-id",
        title="Task",
        prompt=prompt,
        status="PENDING",
    )


def test_registered_project_path_is_accepted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "ALLOWED_PROJECT_PATHS", frozenset({str(tmp_path)}))
    assert validate_project_path(str(tmp_path)) == tmp_path


def test_unregistered_and_traversing_paths_are_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "ALLOWED_PROJECT_PATHS", frozenset({str(tmp_path)}))
    with pytest.raises(AppError, match="Project path is not registered"):
        validate_project_path(f"{tmp_path}/../outside")


@pytest.mark.asyncio
async def test_duplicate_execution_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "ALLOWED_PROJECT_PATHS", frozenset({str(tmp_path)}))
    executor = CodexExecutor()
    session = FakeSession(project(tmp_path), task())
    await executor.reserve(session, "project-id", "task-id")
    with pytest.raises(AppError) as error:
        await executor.reserve(session, "project-id", "task-id")
    assert error.value.code == "TASK_ALREADY_RUNNING"


@pytest.mark.asyncio
async def test_task_without_prompt_cannot_execute(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "ALLOWED_PROJECT_PATHS", frozenset({str(tmp_path)}))
    with pytest.raises(AppError) as error:
        await CodexExecutor().reserve(
            FakeSession(project(tmp_path), task(None)), "project-id", "task-id"
        )
    assert error.value.code == "TASK_PROMPT_REQUIRED"


def test_git_snapshot_parses_file_state_and_content(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_text("new content")
    snapshot = parse_porcelain(b" M changed.txt\0", tmp_path)
    assert snapshot["changed.txt"].status == " M"
    assert snapshot["changed.txt"].digest is not None


def test_file_change_detection_covers_created_modified_and_deleted() -> None:
    before = {
        "modified.py": WorktreeEntry(" M", "old"),
        "deleted.py": WorktreeEntry(" M", "old"),
    }
    after = {
        "created.py": WorktreeEntry("??", "new"),
        "modified.py": WorktreeEntry(" M", "new"),
    }
    assert detect_file_changes(before, after) == [
        (ProjectEventType.FILE_CREATED, "created.py"),
        (ProjectEventType.FILE_DELETED, "deleted.py"),
        (ProjectEventType.FILE_CHANGED, "modified.py"),
    ]


def test_command_activity_is_translated_to_test_and_build_events() -> None:
    assert command_event_type("pytest -q", False) == ProjectEventType.TEST_STARTED
    assert command_event_type("pytest -q", True, True) == ProjectEventType.TEST_PASSED
    assert command_event_type("npm run build", True, False) == ProjectEventType.BUILD_FAILED


def test_agent_failure_summary_is_not_treated_as_success() -> None:
    assert agent_reported_failure("I was unable to complete the requested change.")
    assert not agent_reported_failure("Completed the requested change and tests pass.")


@pytest.mark.asyncio
async def test_codex_command_json_becomes_persisted_event_call(tmp_path: Path) -> None:
    executor = CodexExecutor()
    executor._event = AsyncMock()
    request = ExecutionRequest("project-id", "task-id", tmp_path, "Build it")
    payload = {
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "pytest -q", "exit_code": 0},
    }
    await executor._handle_codex_event(object(), request, payload, "summary")
    call = executor._event.await_args.args
    assert call[2] == ProjectEventType.TEST_PASSED
