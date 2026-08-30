from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models.project import Project
from app.db.models.task import ProjectTask
from app.db.session import create_db_session
from app.schemas.projects import (
    ProjectEventCreate,
    ProjectEventType,
    ProjectStatus,
    TaskAction,
)
from app.services.projects import create_project_event
from app.services.tasks import complete_task, fail_task, start_task

logger = get_logger(__name__)
ALLOWED_PROJECT_PATHS = frozenset(
    {"/srv/projects/ai-playground", "/srv/projects/project-two-web"}
)


@dataclass(frozen=True, slots=True)
class WorktreeEntry:
    status: str
    digest: str | None


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    project_id: str
    task_id: str
    project_path: Path
    prompt: str


def validate_project_path(path: str) -> Path:
    candidate = Path(path)
    if path not in ALLOWED_PROJECT_PATHS or not candidate.is_absolute():
        raise AppError("PROJECT_PATH_NOT_ALLOWED", "Project path is not registered.", 403)
    resolved = candidate.resolve(strict=True)
    if str(resolved) != path or not resolved.is_dir():
        raise AppError("PROJECT_PATH_NOT_ALLOWED", "Project path is not registered.", 403)
    return resolved


def parse_porcelain(data: bytes, root: Path) -> dict[str, WorktreeEntry]:
    records = data.split(b"\0")
    snapshot: dict[str, WorktreeEntry] = {}
    skip_source = False
    for raw in records:
        if not raw:
            continue
        if skip_source:
            skip_source = False
            continue
        text = raw.decode("utf-8", errors="replace")
        if len(text) < 4:
            continue
        status, relative = text[:2], text[3:]
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            skip_source = True
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            continue
        target = root / relative_path
        digest = _file_digest(target)
        snapshot[relative] = WorktreeEntry(status=status, digest=digest)
    return snapshot


def detect_file_changes(
    before: dict[str, WorktreeEntry], after: dict[str, WorktreeEntry]
) -> list[tuple[ProjectEventType, str]]:
    changes: list[tuple[ProjectEventType, str]] = []
    for path in sorted(before.keys() | after.keys()):
        previous, current = before.get(path), after.get(path)
        if previous == current:
            continue
        if current is None or (current and "D" in current.status):
            event_type = ProjectEventType.FILE_DELETED
        elif previous is None and current.status == "??":
            event_type = ProjectEventType.FILE_CREATED
        else:
            event_type = ProjectEventType.FILE_CHANGED
        changes.append((event_type, path))
    return changes


def command_event_type(command: str, completed: bool, succeeded: bool = True) -> ProjectEventType:
    normalized = command.lower()
    if any(token in normalized for token in ("pytest", "unittest", "npm test", "npm run test")):
        if not completed:
            return ProjectEventType.TEST_STARTED
        return ProjectEventType.TEST_PASSED if succeeded else ProjectEventType.TEST_FAILED
    if any(token in normalized for token in ("npm run build", "vite build", "docker build")):
        if not completed:
            return ProjectEventType.BUILD_STARTED
        return ProjectEventType.BUILD_PASSED if succeeded else ProjectEventType.BUILD_FAILED
    return ProjectEventType.COMMAND_COMPLETED if completed else ProjectEventType.COMMAND_STARTED


def agent_reported_failure(summary: str) -> bool:
    normalized = " ".join(summary.lower().split())
    failure_markers = (
        "unable to ",
        "unable to complete",
        "unable to perform",
        "could not complete",
        "couldn't complete",
        "failed to complete",
    )
    return any(marker in normalized for marker in failure_markers)


def _file_digest(path: Path) -> str | None:
    try:
        if path.is_symlink():
            return hashlib.sha256(os.readlink(path).encode()).hexdigest()
        if not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65_536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


class CodexExecutor:
    def __init__(self) -> None:
        self._reserved: set[str] = set()
        self._lock = asyncio.Lock()
        self._settings = get_settings()

    async def reserve(
        self, session: AsyncSession, project_id: str, task_id: str
    ) -> ExecutionRequest:
        project = await session.get(Project, project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
        task = await session.get(ProjectTask, task_id)
        if task is None or task.project_id != project_id:
            raise AppError("TASK_NOT_FOUND", "Task not found for this project.", 404)
        project_path = validate_project_path(project.path)
        if not task.prompt or not task.prompt.strip():
            raise AppError("TASK_PROMPT_REQUIRED", "Task must have a build prompt.", 422)
        async with self._lock:
            if task_id in self._reserved or task.status == "RUNNING":
                raise AppError("TASK_ALREADY_RUNNING", "Task is already running.", 409)
            if task.status != "PENDING":
                raise AppError("INVALID_TASK_STATE", "Only pending tasks can be executed.", 409)
            self._reserved.add(task_id)
        return ExecutionRequest(project_id, task_id, project_path, task.prompt.strip())

    async def execute(self, request: ExecutionRequest) -> None:
        try:
            async with create_db_session() as session:
                await self._execute(session, request)
        except Exception:
            logger.exception(
                "codex_execution_failed",
                extra={"project_id": request.project_id, "task_id": request.task_id},
            )
            await self._mark_unexpected_failure(request)
        finally:
            async with self._lock:
                self._reserved.discard(request.task_id)

    async def _execute(self, session: AsyncSession, request: ExecutionRequest) -> None:
        await start_task(
            session,
            request.project_id,
            request.task_id,
            TaskAction(message="Codex execution started", agent="Codex"),
        )
        await self._event(
            session,
            request,
            ProjectEventType.AGENT_STARTED,
            ProjectStatus.RUNNING,
            "Codex agent started",
        )
        before = await self._worktree_snapshot(request.project_path)
        process = await asyncio.create_subprocess_exec(
            self._settings.codex_cli_path,
            "exec",
            "--ephemeral",
            "--json",
            "--color",
            "never",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(request.project_path),
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._codex_environment(),
        )
        assert process.stdin is not None
        process.stdin.write(request.prompt.encode())
        await process.stdin.drain()
        process.stdin.close()

        summary = "Codex completed the task."
        stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None
        assert process.stdout is not None
        async for raw_line in process.stdout:
            try:
                payload = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            summary = await self._handle_codex_event(session, request, payload, summary)
        return_code = await process.wait()
        if stderr_task is not None:
            await stderr_task

        after = await self._worktree_snapshot(request.project_path)
        for event_type, file_path in detect_file_changes(before, after):
            verb = event_type.value.removeprefix("file_").capitalize()
            await self._event(
                session,
                request,
                event_type,
                ProjectStatus.RUNNING,
                f"{verb} {file_path}",
                file=file_path,
            )

        succeeded = return_code == 0 and not agent_reported_failure(summary)
        if succeeded:
            await self._event(
                session,
                request,
                ProjectEventType.AGENT_FINISHED,
                ProjectStatus.RUNNING,
                "Codex agent finished",
            )
            await complete_task(
                session,
                request.project_id,
                request.task_id,
                TaskAction(
                    message="Codex task completed",
                    agent="Codex",
                    result_summary=summary[:1_000],
                ),
            )
        else:
            await self._event(
                session,
                request,
                ProjectEventType.AGENT_FINISHED,
                ProjectStatus.FAILED,
                "Codex agent stopped",
            )
            await fail_task(
                session,
                request.project_id,
                request.task_id,
                TaskAction(
                    message="Codex task failed",
                    agent="Codex",
                    result_summary=(
                        summary[:1_000]
                        if return_code == 0
                        else f"Codex exited with status {return_code}."
                    ),
                ),
            )

    async def _handle_codex_event(
        self,
        session: AsyncSession,
        request: ExecutionRequest,
        payload: dict[str, Any],
        summary: str,
    ) -> str:
        item = payload.get("item") or {}
        if item.get("type") == "agent_message" and item.get("text"):
            return str(item["text"]).strip()
        if item.get("type") != "command_execution":
            return summary
        command = str(item.get("command") or "command").strip().replace("\n", " ")[:500]
        event_name = str(payload.get("type") or "")
        if event_name == "item.started":
            event_type = command_event_type(command, completed=False)
            await self._event(
                session, request, event_type, ProjectStatus.RUNNING, f"Running: {command}"
            )
        elif event_name == "item.completed":
            succeeded = item.get("exit_code") == 0
            event_type = command_event_type(command, completed=True, succeeded=succeeded)
            status = ProjectStatus.DONE if succeeded else ProjectStatus.FAILED
            message = f"Completed: {command}" if succeeded else f"Failed: {command}"
            await self._event(session, request, event_type, status, message)
        return summary

    async def _worktree_snapshot(self, root: Path) -> dict[str, WorktreeEntry]:
        process = await asyncio.create_subprocess_exec(
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=self._git_environment(),
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            raise AppError(
                "PROJECT_GIT_REQUIRED", "Registered project is not a Git repository.", 422
            )
        return parse_porcelain(stdout, root)

    async def _event(
        self,
        session: AsyncSession,
        request: ExecutionRequest,
        event_type: ProjectEventType,
        status: ProjectStatus,
        message: str,
        file: str | None = None,
    ) -> None:
        await create_project_event(
            session,
            request.project_id,
            ProjectEventCreate(
                task_id=request.task_id,
                type=event_type,
                status=status,
                message=message,
                agent="Codex",
                file=file,
            ),
        )

    async def _mark_unexpected_failure(self, request: ExecutionRequest) -> None:
        async with create_db_session() as session:
            task = await session.get(ProjectTask, request.task_id)
            if task is None or task.status not in {"PENDING", "RUNNING"}:
                return
            await fail_task(
                session,
                request.project_id,
                request.task_id,
                TaskAction(
                    message="Codex execution failed",
                    agent="Codex",
                    result_summary="Codex execution stopped unexpectedly.",
                ),
            )

    def _codex_environment(self) -> dict[str, str]:
        return {
            "HOME": self._settings.codex_home,
            "CODEX_HOME": self._settings.codex_home,
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8",
        }

    @staticmethod
    def _git_environment() -> dict[str, str]:
        return {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}


codex_executor = CodexExecutor()
