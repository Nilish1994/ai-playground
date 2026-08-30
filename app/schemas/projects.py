from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProjectStatus(StrEnum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class BriefStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    BUILDING = "BUILDING"
    DONE = "DONE"


class ProjectEventType(StrEnum):
    TASK_CREATED = "task_created"
    PROMPT_GENERATED = "prompt_generated"
    TASK_STARTED = "task_started"
    AGENT_STARTED = "agent_started"
    AGENT_THINKING = "agent_thinking"
    COMMAND_STARTED = "command_started"
    COMMAND_COMPLETED = "command_completed"
    FILE_CREATED = "file_created"
    FILE_CHANGED = "file_changed"
    FILE_DELETED = "file_deleted"
    TEST_STARTED = "test_started"
    TEST_PASSED = "test_passed"
    TEST_FAILED = "test_failed"
    BUILD_STARTED = "build_started"
    BUILD_PASSED = "build_passed"
    BUILD_FAILED = "build_failed"
    AGENT_FINISHED = "agent_finished"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


class ProjectCheck(BaseModel):
    label: str
    status: ProjectStatus
    detail: str


class ProjectEventCreate(BaseModel):
    type: ProjectEventType
    status: ProjectStatus
    message: str = Field(min_length=1, max_length=2_000)
    task_id: str | None = None
    agent: str | None = Field(default=None, max_length=160)
    file: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectEventRead(ProjectEventCreate):
    event_id: str
    project_id: str
    timestamp: datetime


class ProjectTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    prompt: str | None = None
    agent: str | None = Field(default=None, max_length=160)


class TaskAction(BaseModel):
    message: str | None = Field(default=None, max_length=2_000)
    agent: str | None = Field(default=None, max_length=160)
    result_summary: str | None = None


class ProjectTaskRead(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None
    prompt: str | None
    status: TaskStatus
    agent: str | None
    result_summary: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class ProjectTaskDetail(ProjectTaskRead):
    events: list[ProjectEventRead]


class ProjectBriefCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1)
    decisions: list[str] = Field(default_factory=list)
    build_prompt: str = Field(min_length=1)
    status: BriefStatus = BriefStatus.DRAFT
    task_id: str | None = None


class ProjectBriefUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    summary: str | None = Field(default=None, min_length=1)
    decisions: list[str] | None = None
    build_prompt: str | None = Field(default=None, min_length=1)
    status: BriefStatus | None = None
    task_id: str | None = None


class BriefTaskLink(BaseModel):
    task_id: str | None = None


class ProjectBriefRead(BaseModel):
    id: str
    project_id: str
    title: str
    summary: str
    decisions: list[str]
    build_prompt: str
    status: BriefStatus
    task_id: str | None
    created_at: datetime
    updated_at: datetime


class ProjectRead(BaseModel):
    id: str
    name: str
    path: str
    status: ProjectStatus
    current_task: str | None
    last_completed_task: str | None
    active_agent: str | None
    updated_at: datetime
    recent_files: list[str]
    checks: list[ProjectCheck]
    tasks: list[ProjectTaskRead]
    briefs: list[ProjectBriefRead]
    recent_events: list[ProjectEventRead]


class TaskExecutionAccepted(BaseModel):
    project_id: str
    task_id: str
    status: str = "accepted"


class ProjectEventEnvelope(BaseModel):
    event: ProjectEventRead
    project: ProjectRead
    task: ProjectTaskRead | None = None
