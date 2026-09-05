from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.models.project import Project
from app.schemas.projects import ProjectMemoryRead
from app.services import project_discovery
from app.services.project_discovery import (
    GitMetadata,
    discover_projects,
    onboard_project,
    resolve_trusted_project_path,
)
from app.services.project_events import project_event_broker


class ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class FakeSession:
    def __init__(self, projects: list[Project] | None = None) -> None:
        self.projects = {project.id: project for project in projects or []}
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, key):
        if model is Project:
            return self.projects.get(key)
        return None

    async def scalars(self, _statement):
        return ScalarResult(self.projects.values())

    def add(self, value):
        if isinstance(value, Project):
            self.projects[value.id] = value

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_project(project_id: str, path: Path) -> Project:
    return Project(
        id=project_id,
        name=project_id.replace("-", " ").title(),
        path=str(path),
        status="IDLE",
        updated_at=datetime.now(UTC),
        recent_files=[],
        checks=[],
    )


@pytest.fixture
def persistence_stubs(monkeypatch):
    memories = {}
    events = []

    async def ensure_memory(_session, project_id):
        memories.setdefault(project_id, {})
        return memories[project_id]

    async def update_memory(_session, project_id, payload):
        memories[project_id] = payload.model_dump()
        return ProjectMemoryRead(
            id=f"memory-{project_id}",
            project_id=project_id,
            updated_at=datetime.now(UTC),
            **memories[project_id],
        )

    async def create_event(_session, project_id, payload):
        events.append((project_id, payload))
        return None

    monkeypatch.setattr(project_discovery, "ensure_project_memory", ensure_memory)
    monkeypatch.setattr(project_discovery, "update_memory", update_memory)
    monkeypatch.setattr(project_discovery, "create_project_event", create_event)
    return memories, events


@pytest.mark.asyncio
async def test_valid_project_discovery_creates_default_memory_and_event(
    tmp_path, persistence_stubs
) -> None:
    project_path = tmp_path / "new-tool"
    project_path.mkdir()
    (project_path / "package.json").write_text('{"name":"new-tool"}')
    session = FakeSession()

    result = await discover_projects(session, tmp_path)

    memories, events = persistence_stubs
    assert [item.id for item in result.newly_registered] == ["new-tool"]
    assert memories["new-tool"]["purpose"] == "Not yet identified"
    assert memories["new-tool"]["next_steps"] == ["Run project onboarding audit"]
    assert events[0][0] == "new-tool"
    assert events[0][1].type.value == "project_discovered"


@pytest.mark.asyncio
async def test_duplicate_registration_is_prevented(tmp_path, persistence_stubs) -> None:
    project_path = tmp_path / "known-tool"
    project_path.mkdir()
    (project_path / "Dockerfile").write_text("FROM scratch\n")
    session = FakeSession([make_project("known-tool", project_path)])

    result = await discover_projects(session, tmp_path)

    assert result.newly_registered == []
    assert [item.id for item in result.already_known] == ["known-tool"]
    assert len(session.projects) == 1


@pytest.mark.asyncio
async def test_non_project_and_hidden_folders_are_ignored(tmp_path, persistence_stubs) -> None:
    (tmp_path / "notes").mkdir()
    hidden = tmp_path / ".hidden-project"
    hidden.mkdir()
    (hidden / "pyproject.toml").write_text("[project]\n")
    session = FakeSession()

    result = await discover_projects(session, tmp_path)

    reasons = {item.name: item.reason for item in result.ignored}
    assert reasons["notes"] == "no project marker"
    assert reasons[".hidden-project"] == "hidden or system folder"
    assert result.newly_registered == []


def test_path_traversal_and_nested_paths_are_rejected(tmp_path) -> None:
    outside = tmp_path.parent / "outside-project"
    outside.mkdir(exist_ok=True)
    nested = tmp_path / "group" / "nested"
    nested.mkdir(parents=True)

    with pytest.raises(AppError, match="outside the trusted projects root"):
        resolve_trusted_project_path(tmp_path / ".." / outside.name, tmp_path)
    with pytest.raises(AppError, match="Only direct children"):
        resolve_trusted_project_path(nested, tmp_path)


def test_symlink_escape_is_rejected(tmp_path) -> None:
    outside = tmp_path.parent / "symlink-target"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "escaped-project"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(AppError, match="Symbolic-link"):
        resolve_trusted_project_path(link, tmp_path)


@pytest.mark.asyncio
async def test_slug_collision_gets_stable_suffix(tmp_path, persistence_stubs) -> None:
    first = tmp_path / "new tool"
    second = tmp_path / "new-tool"
    first.mkdir()
    second.mkdir()
    (first / "package.json").write_text("{}")
    (second / "package.json").write_text("{}")
    session = FakeSession()

    result = await discover_projects(session, tmp_path)

    ids = {item.id for item in result.newly_registered}
    assert "new-tool" in ids
    assert len(ids) == 2
    assert any(value.startswith("new-tool-") for value in ids)


@pytest.mark.asyncio
async def test_onboarding_is_read_only_and_avoids_secrets(
    tmp_path, monkeypatch, persistence_stubs
) -> None:
    project_path = tmp_path / "safe-project"
    project_path.mkdir()
    (project_path / "README.md").write_text("# Safe Project\nA small service.\n")
    (project_path / "pyproject.toml").write_text('dependencies = ["fastapi"]\n')
    (project_path / "AGENTS.md").write_text("Keep changes focused.\n")
    (project_path / ".env").write_text("SECRET=must-not-be-read\n")
    data_file = project_path / "staffing.csv"
    data_file.write_text("employee,shift\nPrivate Person,08:00\n")
    before = {path.name: path.read_bytes() for path in project_path.iterdir() if path.is_file()}
    project = make_project("safe-project", project_path)
    session = FakeSession([project])

    async def get_project(_session, project_id):
        memory_data = persistence_stubs[0][project_id]
        return {
            "id": project_id,
            "name": project.name,
            "path": project.path,
            "status": "IDLE",
            "current_task": None,
            "last_completed_task": None,
            "active_agent": None,
            "updated_at": datetime.now(UTC),
            "recent_files": [],
            "checks": [],
            "memory": {
                "id": f"memory-{project_id}",
                "project_id": project_id,
                "updated_at": datetime.now(UTC),
                **memory_data,
            },
            "tasks": [],
            "briefs": [],
            "recent_events": [],
        }

    monkeypatch.setattr(project_discovery, "get_project", get_project)
    monkeypatch.setattr(
        project_discovery,
        "_git_metadata",
        lambda _path: GitMetadata("main", True, "Initial commit"),
    )

    result = await onboard_project(session, "safe-project", tmp_path)

    after = {path.name: path.read_bytes() for path in project_path.iterdir() if path.is_file()}
    assert before == after
    assert result.inspected_files == ["AGENTS.md", "README.md", "pyproject.toml"]
    assert ".env" not in result.top_level_entries
    assert "staffing.csv" in result.top_level_entries
    saved = persistence_stubs[0]["safe-project"]
    assert "must-not-be-read" not in str(saved)
    assert "Private Person" not in str(saved)
    assert saved["architecture_summary"] == "FastAPI"
    assert persistence_stubs[1][-1][1].type.value == "memory_updated"
    assert persistence_stubs[1][-1][1].metadata == {"source": "read_only_onboarding"}


@pytest.mark.asyncio
async def test_onboarding_updates_only_the_selected_project(
    tmp_path, monkeypatch, persistence_stubs
) -> None:
    first_path = tmp_path / "first"
    second_path = tmp_path / "second"
    first_path.mkdir()
    second_path.mkdir()
    (first_path / "README.md").write_text("# First project\n")
    (second_path / "README.md").write_text("# Second project\n")
    session = FakeSession([make_project("first", first_path), make_project("second", second_path)])

    async def get_project(_session, project_id):
        return {
            "id": project_id,
            "name": project_id.title(),
            "path": str(first_path if project_id == "first" else second_path),
            "status": "IDLE",
            "current_task": None,
            "last_completed_task": None,
            "active_agent": None,
            "updated_at": datetime.now(UTC),
            "recent_files": [],
            "checks": [],
            "memory": None,
            "tasks": [],
            "briefs": [],
            "recent_events": [],
        }

    monkeypatch.setattr(project_discovery, "get_project", get_project)
    monkeypatch.setattr(
        project_discovery,
        "_git_metadata",
        lambda _path: GitMetadata(None, None, None),
    )

    await onboard_project(session, "first", tmp_path)

    assert set(persistence_stubs[0]) == {"first"}
    assert persistence_stubs[0]["first"]["purpose"] == "First project"


@pytest.mark.asyncio
async def test_project_event_broker_delivers_discovery_event() -> None:
    event = object()
    async with project_event_broker.subscribe() as queue:
        project_event_broker.publish(event)
        assert await queue.get() is event
