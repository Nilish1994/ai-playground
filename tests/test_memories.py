from datetime import UTC, datetime

import pytest

from app.db.models.brief import ProjectBrief
from app.db.models.memory import ProjectMemory
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.schemas.projects import ProjectMemoryUpdate
from app.services.memories import ensure_project_memory, get_project_context, update_memory


class FakeSession:
    def __init__(self, projects: list[Project]) -> None:
        self.projects = {project.id: project for project in projects}
        self.memories: dict[str, ProjectMemory] = {}
        self.briefs: list[ProjectBrief] = []
        self.tasks: list[ProjectTask] = []
        self.commit_count = 0

    async def get(self, model, key):
        if model is Project:
            return self.projects.get(key)
        return None

    async def execute(self, statement):
        params = statement.compile().params
        project_id = params["project_id"]
        if project_id not in self.memories:
            self.memories[project_id] = ProjectMemory(
                id=params["id"],
                project_id=project_id,
                purpose="",
                current_state="",
                architecture_summary="",
                important_decisions=[],
                coding_rules=[],
                current_focus="",
                next_steps=[],
                updated_at=datetime.now(UTC),
            )

    async def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        project_id = next(value for key, value in params.items() if key.startswith("project_id"))
        if entity is ProjectMemory:
            return self.memories.get(project_id)
        collection = self.briefs if entity is ProjectBrief else self.tasks
        allowed_statuses = {"READY", "BUILDING"} if entity is ProjectBrief else {"RUNNING"}
        return next(
            (
                item
                for item in collection
                if item.project_id == project_id and item.status in allowed_statuses
            ),
            None,
        )

    async def commit(self):
        self.commit_count += 1


def project(project_id: str) -> Project:
    return Project(
        id=project_id,
        name=project_id.title(),
        path=f"/srv/projects/{project_id}",
        status="IDLE",
        recent_files=[],
        checks=[],
    )


@pytest.mark.asyncio
async def test_memory_is_created_for_a_new_project() -> None:
    session = FakeSession([project("new-project")])
    memory = await ensure_project_memory(session, "new-project")
    assert memory.project_id == "new-project"
    assert memory.purpose == ""


@pytest.mark.asyncio
async def test_one_memory_is_reused_per_project() -> None:
    session = FakeSession([project("project-one")])
    first = await ensure_project_memory(session, "project-one")
    second = await ensure_project_memory(session, "project-one")
    assert first.id == second.id
    assert len(session.memories) == 1
    assert ProjectMemory.__table__.c.project_id.unique is True


@pytest.mark.asyncio
async def test_memory_update_is_persisted() -> None:
    session = FakeSession([project("project-one")])
    result = await update_memory(
        session,
        "project-one",
        ProjectMemoryUpdate(
            purpose="A focused project",
            current_focus="Ship memory",
            next_steps=["Use concise context"],
        ),
    )
    assert result.purpose == "A focused project"
    assert result.current_focus == "Ship memory"
    assert result.next_steps == ["Use concise context"]


@pytest.mark.asyncio
async def test_project_memories_are_isolated() -> None:
    session = FakeSession([project("project-one"), project("project-two")])
    await update_memory(session, "project-one", ProjectMemoryUpdate(purpose="Only project one"))
    second = await ensure_project_memory(session, "project-two")
    assert second.purpose == ""
    assert session.memories["project-one"].purpose == "Only project one"


@pytest.mark.asyncio
async def test_context_builder_returns_only_requested_project_context() -> None:
    now = datetime.now(UTC)
    session = FakeSession([project("project-one"), project("project-two")])
    await update_memory(session, "project-one", ProjectMemoryUpdate(purpose="Project one memory"))
    await update_memory(session, "project-two", ProjectMemoryUpdate(purpose="Project two memory"))
    session.briefs = [
        ProjectBrief(
            id="brief-one",
            project_id="project-one",
            title="One brief",
            summary="Only one",
            decisions=[],
            build_prompt="Build one",
            status="READY",
            created_at=now,
            updated_at=now,
        ),
        ProjectBrief(
            id="brief-two",
            project_id="project-two",
            title="Two brief",
            summary="Only two",
            decisions=[],
            build_prompt="Build two",
            status="BUILDING",
            created_at=now,
            updated_at=now,
        ),
    ]
    session.tasks = [
        ProjectTask(
            id="task-one",
            project_id="project-one",
            title="One task",
            status="RUNNING",
            created_at=now,
            updated_at=now,
        ),
        ProjectTask(
            id="task-two",
            project_id="project-two",
            title="Two task",
            status="RUNNING",
            created_at=now,
            updated_at=now,
        ),
    ]

    context = await get_project_context(session, "project-one")

    assert context.project_id == "project-one"
    assert context.memory.purpose == "Project one memory"
    assert context.active_brief and context.active_brief.id == "brief-one"
    assert context.current_task and context.current_task.id == "task-one"
    assert not hasattr(context, "events")
