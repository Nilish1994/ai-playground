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
