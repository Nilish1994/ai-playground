from __future__ import annotations

from app.schemas.projects import ProjectContext


def _text(value: str | None, limit: int = 1_000) -> str:
    return " ".join((value or "").split())[:limit]


def _list_section(title: str, values: list[str]) -> list[str]:
    items = [_text(value, 400) for value in values[:10] if _text(value, 400)]
    return [title, *(f"- {item}" for item in items)] if items else []


def build_codex_prompt(project_context: ProjectContext, task_prompt: str) -> str:
    """Build concise, project-scoped context for a single Codex execution."""
    memory = project_context.memory
    sections: list[list[str]] = [
        [
            "PROJECT",
            f"Name: {_text(project_context.project_name, 240)}",
            f"Purpose: {_text(memory.purpose)}" if memory.purpose else "",
        ],
        [
            "CURRENT STATE",
            _text(memory.current_state),
            f"Current focus: {_text(memory.current_focus)}" if memory.current_focus else "",
        ],
        ["ARCHITECTURE", _text(memory.architecture_summary, 1_500)],
        _list_section("IMPORTANT DECISIONS", memory.important_decisions),
        _list_section("CODING RULES", memory.coding_rules),
    ]

    if project_context.active_brief is not None:
        brief = project_context.active_brief
        sections.append(
            [
                "ACTIVE BRIEF",
                f"Title: {_text(brief.title, 240)}",
                f"Summary: {_text(brief.summary)}",
                *_list_section("Decisions:", brief.decisions)[1:],
            ]
        )

    if project_context.current_task is not None:
        task = project_context.current_task
        sections.append(
            [
                "CURRENT TASK",
                f"Title: {_text(task.title, 240)}",
                f"Description: {_text(task.description)}" if task.description else "",
            ]
        )

    sections.append(["USER REQUEST", task_prompt.strip()])
    return "\n\n".join(
        "\n".join(line for line in section if line) for section in sections if any(section)
    )
