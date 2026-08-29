from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.db.models.brief import ProjectBrief
from app.schemas.projects import BriefStatus, ProjectBriefCreate, ProjectBriefUpdate
from app.services.briefs import apply_brief_updates


def brief() -> ProjectBrief:
    return ProjectBrief(
        id="brief-id",
        project_id="project-id",
        title="Initial title",
        summary="Initial summary",
        decisions=["Keep it simple"],
        build_prompt="Build the initial feature",
        status="DRAFT",
        task_id="task-id",
    )


def test_brief_update_changes_only_supplied_fields() -> None:
    item = brief()
    timestamp = datetime.now(UTC)

    apply_brief_updates(
        item,
        ProjectBriefUpdate(status=BriefStatus.READY, decisions=["Use PostgreSQL"]),
        timestamp,
    )

    assert item.title == "Initial title"
    assert item.status == "READY"
    assert item.decisions == ["Use PostgreSQL"]
    assert item.updated_at == timestamp


def test_brief_update_can_unlink_task() -> None:
    item = brief()
    apply_brief_updates(item, ProjectBriefUpdate(task_id=None), datetime.now(UTC))
    assert item.task_id is None


def test_create_brief_requires_compact_core_content() -> None:
    with pytest.raises(ValidationError):
        ProjectBriefCreate(title="", summary="", build_prompt="")
