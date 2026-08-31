from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.errors import AppError
from app.db.models.memory import ProjectMemory
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.schemas.projects import ProjectEventType
from app.services import memory_refresh as refresh_module
from app.services.memory_refresh import MemoryRefreshProposal, refresh_project_memory_after_task

NOW = datetime.now(UTC)


class FakeSession:
    def __init__(self, projects: list[Project], tasks: list[ProjectTask]) -> None:
        self.projects = {item.id: item for item in projects}
        self.tasks = {item.id: item for item in tasks}
        self.brief = None
        self.commit_count = 0

    async def get(self, model, key):
        if model is Project:
            return self.projects.get(key)
        if model is ProjectTask:
            return self.tasks.get(key)
        return None

    async def scalar(self, _statement):
        return self.brief

    async def commit(self):
        self.commit_count += 1


def project(project_id: str) -> Project:
    return Project(
        id=project_id,
        name=project_id.replace("-", " ").title(),
        path=f"/srv/projects/{project_id}",
        status="DONE",
        recent_files=[],
        checks=[],
    )


def task(
    project_id: str,
    *,
    status: str = "DONE",
    updates_memory: bool = True,
) -> ProjectTask:
    return ProjectTask(
        id=f"task-{project_id}",
        project_id=project_id,
        title="Add durable project capability",
        description="Implement a concise capability.",
        status=status,
        agent="Codex",
        result_summary="The capability is implemented and validated.",
        updates_memory=updates_memory,
        created_at=NOW,
        updated_at=NOW,
    )


def memory(project_id: str) -> ProjectMemory:
    return ProjectMemory(
        id=f"memory-{project_id}",
        project_id=project_id,
        purpose="Stable purpose",
        current_state="Previous state",
        architecture_summary="FastAPI and PostgreSQL",
        important_decisions=["Keep history separate"],
        coding_rules=["Keep services modular"],
        current_focus="Previous focus",
        next_steps=["Implement capability"],
        updated_at=NOW,
    )


def proposal(**changes) -> MemoryRefreshProposal:
    values = {
        "current_state": "Previous state",
        "architecture_summary": "FastAPI and PostgreSQL",
        "important_decisions": ["Keep history separate"],
        "coding_rules": ["Keep services modular"],
        "current_focus": "Previous focus",
        "next_steps": ["Implement capability"],
    }
    values.update(changes)
    return MemoryRefreshProposal(**values)


class FakeGenerator:
    def __init__(self, result) -> None:
        self.result = result
        self.inputs: list[str] = []

    async def generate(self, input_text: str):
        self.inputs.append(input_text)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def prepare(monkeypatch, project_id: str = "ai-playground"):
    item_project = project(project_id)
    item_task = task(project_id)
    item_memory = memory(project_id)
    session = FakeSession([item_project], [item_task])
    monkeypatch.setattr(
        refresh_module,
        "ensure_project_memory",
        AsyncMock(return_value=item_memory),
    )
    create_event = AsyncMock()
    monkeypatch.setattr(refresh_module, "create_project_event", create_event)
    return session, item_task, item_memory, create_event


@pytest.mark.asyncio
async def test_meaningful_done_task_refreshes_memory_and_emits_event(monkeypatch) -> None:
    session, item_task, item_memory, create_event = prepare(monkeypatch)
    generator = FakeGenerator(
        proposal(
            current_state="Capability is operational.",
            current_focus="Use the new capability.",
            next_steps=["Monitor real use"],
        )
    )

    changed = await refresh_project_memory_after_task(
        session, "ai-playground", item_task.id, generator
    )

    assert changed is True
    assert item_memory.current_state == "Capability is operational."
    assert item_memory.purpose == "Stable purpose"
    assert item_task.memory_refresh_attempted_at is not None
    assert item_task.memory_refresh_completed_at is not None
    event = create_event.await_args.args[2]
    assert event.type == ProjectEventType.MEMORY_UPDATED
    assert event.message == "Project memory refreshed after completed task."
    assert "project_events" not in generator.inputs[0]
    assert "raw event" not in generator.inputs[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "updates_memory"),
    [("DONE", False), ("FAILED", True)],
)
async def test_ineligible_task_does_not_refresh(
    monkeypatch, status: str, updates_memory: bool
) -> None:
    session, item_task, item_memory, create_event = prepare(monkeypatch)
    item_task.status = status
    item_task.updates_memory = updates_memory
    generator = FakeGenerator(proposal(current_state="Should not apply"))

    changed = await refresh_project_memory_after_task(
        session, "ai-playground", item_task.id, generator
    )

    assert changed is False
    assert item_memory.current_state == "Previous state"
    assert generator.inputs == []
    create_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_project", "requested_project"),
    [("ai-playground", "office-project"), ("office-project", "ai-playground")],
)
async def test_project_isolation_rejects_cross_project_refresh(
    monkeypatch, task_project: str, requested_project: str
) -> None:
    own_memory = memory(task_project)
    other_memory = memory(requested_project)
    item_task = task(task_project)
    session = FakeSession(
        [project(task_project), project(requested_project)],
        [item_task],
    )
    ensure_memory = AsyncMock(return_value=own_memory)
    monkeypatch.setattr(refresh_module, "ensure_project_memory", ensure_memory)

    with pytest.raises(AppError) as error:
        await refresh_project_memory_after_task(
            session, requested_project, item_task.id, FakeGenerator(proposal())
        )

    assert error.value.code == "TASK_NOT_FOUND"
    assert own_memory.current_state == "Previous state"
    assert other_memory.current_state == "Previous state"
    ensure_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_unchanged_proposal_preserves_memory_without_event(monkeypatch) -> None:
    session, item_task, item_memory, create_event = prepare(monkeypatch)

    changed = await refresh_project_memory_after_task(
        session, "ai-playground", item_task.id, FakeGenerator(proposal())
    )

    assert changed is False
    assert item_memory.current_state == "Previous state"
    assert item_memory.important_decisions == ["Keep history separate"]
    assert item_task.memory_refresh_completed_at is not None
    create_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        {"current_state": "Incomplete output"},
        RuntimeError("model unavailable"),
    ],
)
async def test_invalid_output_or_model_failure_keeps_memory_and_task_done(
    monkeypatch, result
) -> None:
    session, item_task, item_memory, create_event = prepare(monkeypatch)

    changed = await refresh_project_memory_after_task(
        session, "ai-playground", item_task.id, FakeGenerator(result)
    )

    assert changed is False
    assert item_memory.current_state == "Previous state"
    assert item_task.status == "DONE"
    assert item_task.memory_refresh_attempted_at is not None
    assert item_task.memory_refresh_completed_at is None
    create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_refresh_is_processed_only_once(monkeypatch) -> None:
    session, item_task, _, create_event = prepare(monkeypatch)
    generator = FakeGenerator(proposal(current_state="New state"))

    first = await refresh_project_memory_after_task(
        session, "ai-playground", item_task.id, generator
    )
    second = await refresh_project_memory_after_task(
        session, "ai-playground", item_task.id, generator
    )

    assert first is True
    assert second is False
    assert len(generator.inputs) == 1
    create_event.assert_awaited_once()
