from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.schemas.projects import (
    BriefStatus,
    ProjectBriefRead,
    ProjectContext,
    ProjectEventType,
    ProjectMemoryRead,
    ProjectTaskRead,
    TaskStatus,
)
from app.services import codex_executor as executor_module
from app.services.codex_executor import CodexExecutor, ExecutionRequest
from app.services.codex_prompts import build_codex_prompt

NOW = datetime.now(UTC)


def context(
    project_id: str = "ai-playground",
    project_name: str = "AI Playground",
    *,
    purpose: str = "Personal AI control room",
    active_brief: bool = True,
) -> ProjectContext:
    brief = None
    if active_brief:
        brief = ProjectBriefRead(
            id=f"brief-{project_id}",
            project_id=project_id,
            title="Connect executor context",
            summary="Orient Codex with concise project context.",
            decisions=["Do not include raw event history."],
            build_prompt="Internal brief prompt",
            status=BriefStatus.READY,
            task_id=None,
            created_at=NOW,
            updated_at=NOW,
        )
    return ProjectContext(
        project_id=project_id,
        project_name=project_name,
        memory=ProjectMemoryRead(
            id=f"memory-{project_id}",
            project_id=project_id,
            purpose=purpose,
            current_state="Task execution is operational.",
            architecture_summary="FastAPI, PostgreSQL, React, SSE and Codex.",
            important_decisions=["PostgreSQL is the source of truth."],
            coding_rules=["Keep project contexts isolated."],
            current_focus="Load context before execution.",
            next_steps=["Test the integration."],
            updated_at=NOW,
        ),
        active_brief=brief,
        current_task=ProjectTaskRead(
            id=f"task-{project_id}",
            project_id=project_id,
            title="Integrate context",
            description="Assemble a concise Codex prompt.",
            prompt="Original task prompt",
            status=TaskStatus.RUNNING,
            agent="Codex",
            result_summary=None,
            created_at=NOW,
            started_at=NOW,
            completed_at=None,
            updated_at=NOW,
        ),
    )


def test_prompt_contains_memory_coding_rules_brief_and_user_request() -> None:
    prompt = build_codex_prompt(context(), "Add automatic project discovery.")
    assert "Personal AI control room" in prompt
    assert "Keep project contexts isolated." in prompt
    assert "ACTIVE BRIEF" in prompt
    assert "Connect executor context" in prompt
    assert prompt.endswith("USER REQUEST\nAdd automatic project discovery.")


def test_prompt_works_without_memory_content_or_active_brief() -> None:
    value = context(purpose="", active_brief=False)
    value.memory.current_state = ""
    value.memory.architecture_summary = ""
    value.memory.important_decisions = []
    value.memory.coding_rules = []
    value.memory.current_focus = ""
    prompt = build_codex_prompt(value, "Run the task")
    assert "ACTIVE BRIEF" not in prompt
    assert "Run the task" in prompt
    assert "AI Playground" in prompt


def test_project_context_does_not_leak_between_projects() -> None:
    office = context(
        "office-project",
        "Office Project",
        purpose="SECRET_OFFICE_CONTEXT",
        active_brief=False,
    )
    ai_prompt = build_codex_prompt(context(active_brief=False), "Build AI feature")
    office_prompt = build_codex_prompt(office, "Build office feature")
    assert "SECRET_OFFICE_CONTEXT" not in ai_prompt
    assert "Personal AI control room" not in office_prompt


def test_raw_event_history_is_not_part_of_codex_prompt() -> None:
    project_context = context()
    assert not hasattr(project_context, "events")
    prompt = build_codex_prompt(project_context, "Do useful work")
    assert "SECRET_RAW_EVENT_MESSAGE" not in prompt
    assert "project_events" not in prompt


@pytest.mark.asyncio
async def test_executor_loads_context_and_emits_safe_event_before_execution(monkeypatch) -> None:
    project_context = context()
    get_context = AsyncMock(return_value=project_context)
    monkeypatch.setattr(executor_module, "get_project_context", get_context)
    executor = CodexExecutor()
    executor._event = AsyncMock()
    request = ExecutionRequest(
        "ai-playground",
        "task-ai-playground",
        Path("/srv/projects/ai-playground"),
        "Original task prompt",
    )

    session = object()
    prompt = await executor._load_context_prompt(session, request)

    get_context.assert_awaited_once_with(session, "ai-playground")
    assert "Personal AI control room" in prompt
    assert request.prompt == "Original task prompt"
    event_args = executor._event.await_args.args
    assert event_args[2] == ProjectEventType.CONTEXT_LOADED
    assert event_args[4] == "Loaded concise AI Playground project context for Codex execution."
    assert "Personal AI control room" not in event_args[4]


@pytest.mark.asyncio
async def test_sequential_executions_load_only_their_own_project_context(monkeypatch) -> None:
    ai_context = context(
        purpose="AI Playground unique context",
        active_brief=False,
    )
    office_context = context(
        "office-project",
        "Office Project",
        purpose="Office Project unique context",
        active_brief=False,
    )
    get_context = AsyncMock(side_effect=[ai_context, office_context])
    monkeypatch.setattr(executor_module, "get_project_context", get_context)
    executor = CodexExecutor()
    executor._event = AsyncMock()
    session = object()
    ai_request = ExecutionRequest(
        "ai-playground",
        "task-ai",
        Path("/srv/projects/ai-playground"),
        "Build AI feature",
    )
    office_request = ExecutionRequest(
        "office-project",
        "task-office",
        Path("/srv/projects/project-two-web"),
        "Build office feature",
    )

    ai_prompt = await executor._load_context_prompt(session, ai_request)
    office_prompt = await executor._load_context_prompt(session, office_request)

    assert "AI Playground unique context" in ai_prompt
    assert "Office Project unique context" not in ai_prompt
    assert "Office Project unique context" in office_prompt
    assert "AI Playground unique context" not in office_prompt
    assert get_context.await_args_list[0].args == (session, "ai-playground")
    assert get_context.await_args_list[1].args == (session, "office-project")
    assert executor._event.await_args_list[0].args[1] is ai_request
    assert executor._event.await_args_list[1].args[1] is office_request


class _FakeStdin:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data: bytes) -> None:
        self.data += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


class _EmptyStdout:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _FakeProcess:
    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _EmptyStdout()
        self.stderr = None

    async def wait(self) -> int:
        return 0


@pytest.mark.asyncio
async def test_sequential_executions_launch_with_each_registered_working_directory(
    monkeypatch,
) -> None:
    processes = [_FakeProcess(), _FakeProcess()]
    launch = AsyncMock(side_effect=processes)
    monkeypatch.setattr(executor_module.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(executor_module, "start_task", AsyncMock())
    monkeypatch.setattr(executor_module, "complete_task", AsyncMock())
    executor = CodexExecutor()
    executor._load_context_prompt = AsyncMock(side_effect=["AI prompt", "Office prompt"])
    executor._worktree_snapshot = AsyncMock(side_effect=[{}, {}, {}, {}])
    executor._event = AsyncMock()
    session = object()
    requests = [
        ExecutionRequest(
            "ai-playground",
            "task-ai",
            Path("/srv/projects/ai-playground"),
            "AI task",
        ),
        ExecutionRequest(
            "office-project",
            "task-office",
            Path("/srv/projects/project-two-web"),
            "Office task",
        ),
    ]

    for request in requests:
        await executor._execute(session, request)

    first_args = launch.await_args_list[0].args
    second_args = launch.await_args_list[1].args
    assert first_args[first_args.index("--cd") + 1] == "/srv/projects/ai-playground"
    assert second_args[second_args.index("--cd") + 1] == "/srv/projects/project-two-web"
    assert processes[0].stdin.data == b"AI prompt"
    assert processes[1].stdin.data == b"Office prompt"
    assert all(call.args[1] is requests[0] for call in executor._event.await_args_list[:2])
    assert all(call.args[1] is requests[1] for call in executor._event.await_args_list[2:])


@pytest.mark.asyncio
async def test_sequential_events_keep_their_project_and_task_ids(monkeypatch) -> None:
    create_event = AsyncMock()
    monkeypatch.setattr(executor_module, "create_project_event", create_event)
    executor = CodexExecutor()
    session = object()
    ai_request = ExecutionRequest(
        "ai-playground", "task-ai", Path("/srv/projects/ai-playground"), "AI task"
    )
    office_request = ExecutionRequest(
        "office-project",
        "task-office",
        Path("/srv/projects/project-two-web"),
        "Office task",
    )

    await executor._event(
        session,
        ai_request,
        ProjectEventType.AGENT_STARTED,
        executor_module.ProjectStatus.RUNNING,
        "AI event",
    )
    await executor._event(
        session,
        office_request,
        ProjectEventType.AGENT_STARTED,
        executor_module.ProjectStatus.RUNNING,
        "Office event",
    )

    first = create_event.await_args_list[0]
    second = create_event.await_args_list[1]
    assert first.args[1] == "ai-playground"
    assert first.args[2].task_id == "task-ai"
    assert second.args[1] == "office-project"
    assert second.args[2].task_id == "task-office"
