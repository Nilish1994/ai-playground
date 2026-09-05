from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.project import Project
from app.schemas.projects import (
    DiscoveredProject,
    IgnoredProjectFolder,
    ProjectDiscoveryResult,
    ProjectEventCreate,
    ProjectEventType,
    ProjectGitInfo,
    ProjectMemoryUpdate,
    ProjectOnboardingResult,
    ProjectStatus,
)
from app.services.memories import ensure_project_memory, update_memory
from app.services.projects import create_project_event, get_project

PROJECT_MARKERS = (
    ".git",
    "pyproject.toml",
    "package.json",
    "Dockerfile",
    "compose.yaml",
    "docker-compose.yml",
)
ONBOARDING_FILES = (
    "README.md",
    "README.rst",
    "README.txt",
    "AGENTS.md",
    "PROJECT.md",
    "package.json",
    "pyproject.toml",
    "Dockerfile",
    "compose.yaml",
    "docker-compose.yml",
)
MAX_ONBOARDING_FILE_BYTES = 128_000
IGNORED_FOLDER_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".cache",
}
SECRET_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}


@dataclass(frozen=True)
class GitMetadata:
    branch: str | None
    clean: bool | None
    latest_commit: str | None


def resolve_trusted_project_path(path: str | Path, trusted_root: str | Path) -> Path:
    try:
        root = Path(trusted_root).resolve(strict=True)
    except OSError as exc:
        raise AppError(
            "PROJECTS_ROOT_UNAVAILABLE", "Trusted projects root is unavailable.", 503
        ) from exc

    candidate = Path(path)
    if candidate.is_symlink():
        raise AppError(
            "UNTRUSTED_PROJECT_PATH", "Symbolic-link project paths are not allowed.", 400
        )
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise AppError(
            "UNTRUSTED_PROJECT_PATH",
            "Project path is outside the trusted projects root.",
            400,
        ) from exc
    if resolved.parent != root:
        raise AppError(
            "UNTRUSTED_PROJECT_PATH",
            "Only direct children of the trusted projects root are allowed.",
            400,
        )
    if not resolved.is_dir():
        raise AppError("INVALID_PROJECT_PATH", "Project path is not a directory.", 400)
    return resolved


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64] or "project"


def _display_name(folder_name: str) -> str:
    return re.sub(r"[-_]+", " ", folder_name).strip().title()


def _project_marker(path: Path) -> str | None:
    return next((marker for marker in PROJECT_MARKERS if (path / marker).exists()), None)


def _project_schema(project: Project) -> DiscoveredProject:
    return DiscoveredProject(id=project.id, name=project.name, path=project.path)


async def _available_project_id(session: AsyncSession, base_slug: str, resolved_path: Path) -> str:
    existing = await session.get(Project, base_slug)
    if existing is None or Path(existing.path).resolve() == resolved_path:
        return base_slug
    suffix = hashlib.sha256(str(resolved_path).encode()).hexdigest()[:8]
    candidate = f"{base_slug[:55]}-{suffix}"
    collision = await session.get(Project, candidate)
    if collision is not None and Path(collision.path).resolve() != resolved_path:
        raise AppError("PROJECT_ID_COLLISION", "A safe project id could not be generated.", 409)
    return candidate


async def discover_projects(
    session: AsyncSession, trusted_root: str | Path = "/srv/projects"
) -> ProjectDiscoveryResult:
    try:
        root = Path(trusted_root).resolve(strict=True)
        children = sorted(root.iterdir(), key=lambda item: item.name.lower())
    except OSError as exc:
        raise AppError(
            "PROJECTS_ROOT_UNAVAILABLE", "Trusted projects root is unavailable.", 503
        ) from exc

    registered = (await session.scalars(select(Project))).all()
    known = {Path(project.path).resolve(): project for project in registered}
    newly_registered: list[DiscoveredProject] = []
    already_known: list[DiscoveredProject] = []
    ignored: list[IgnoredProjectFolder] = []
    errors: list[str] = []

    for child in children:
        if child.name.startswith(".") or child.name in IGNORED_FOLDER_NAMES:
            ignored.append(IgnoredProjectFolder(name=child.name, reason="hidden or system folder"))
            continue
        try:
            resolved = resolve_trusted_project_path(child, root)
        except AppError as exc:
            ignored.append(IgnoredProjectFolder(name=child.name, reason=exc.code.lower()))
            continue
        if resolved in known:
            already_known.append(_project_schema(known[resolved]))
            continue
        marker = _project_marker(resolved)
        if marker is None:
            ignored.append(IgnoredProjectFolder(name=child.name, reason="no project marker"))
            continue

        try:
            project_id = await _available_project_id(session, _slug(child.name), resolved)
            project = Project(
                id=project_id,
                name=_display_name(child.name),
                path=str(resolved),
                status="IDLE",
                recent_files=[],
                checks=[],
            )
            session.add(project)
            await session.commit()
            await ensure_project_memory(session, project_id)
            await update_memory(
                session,
                project_id,
                ProjectMemoryUpdate(
                    purpose="Not yet identified",
                    current_state="Project discovered but not yet onboarded",
                    current_focus="Review project",
                    next_steps=["Run project onboarding audit"],
                ),
            )
            newly_registered.append(_project_schema(project))
            known[resolved] = project
            await create_project_event(
                session,
                project_id,
                ProjectEventCreate(
                    type=ProjectEventType.PROJECT_DISCOVERED,
                    status=ProjectStatus.IDLE,
                    message="Project discovered and registered.",
                    metadata={"marker": marker},
                ),
            )
        except Exception as exc:  # One unreadable folder must not stop the whole scan.
            await session.rollback()
            errors.append(f"{child.name}: {type(exc).__name__}")

    return ProjectDiscoveryResult(
        newly_registered=newly_registered,
        already_known=already_known,
        ignored=ignored,
        errors=errors,
    )


def _read_allowed_files(project_path: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in ONBOARDING_FILES:
        path = project_path / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size > MAX_ONBOARDING_FILE_BYTES:
                continue
            files[name] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return files


def _safe_top_level_entries(project_path: Path) -> list[str]:
    entries = []
    for entry in sorted(project_path.iterdir(), key=lambda item: item.name.lower()):
        if (
            entry.name.startswith(".")
            or entry.name in IGNORED_FOLDER_NAMES
            or entry.name.lower() in SECRET_FILE_NAMES
            or entry.is_symlink()
        ):
            continue
        entries.append(f"{entry.name}/" if entry.is_dir() else entry.name)
        if len(entries) == 50:
            break
    return entries


def _git_command(project_path: Path, *arguments: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), *arguments],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout.strip()


def _git_metadata(project_path: Path) -> GitMetadata:
    if not (project_path / ".git").exists():
        return GitMetadata(branch=None, clean=None, latest_commit=None)
    branch_ok, branch = _git_command(project_path, "branch", "--show-current")
    status_ok, status = _git_command(project_path, "status", "--porcelain")
    commit_ok, commit = _git_command(project_path, "log", "-1", "--pretty=%s")
    return GitMetadata(
        branch=branch if branch_ok and branch else None,
        clean=status == "" if status_ok else None,
        latest_commit=commit if commit_ok and commit else None,
    )


def _architecture(files: dict[str, str]) -> list[str]:
    facts: list[str] = []
    package = files.get("package.json")
    if package:
        try:
            document = json.loads(package)
            dependencies = {
                **document.get("dependencies", {}),
                **document.get("devDependencies", {}),
            }
            for name, label in (
                ("react", "React"),
                ("vite", "Vite"),
                ("typescript", "TypeScript"),
            ):
                if name in dependencies:
                    facts.append(label)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    pyproject = files.get("pyproject.toml", "").lower()
    for token, label in (
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pytest", "Pytest"),
    ):
        if token in pyproject:
            facts.append(label)
    if any(name in files for name in ("Dockerfile", "compose.yaml", "docker-compose.yml")):
        facts.append("Docker")
    return list(dict.fromkeys(facts))


def _purpose(files: dict[str, str], project_name: str) -> str:
    package = files.get("package.json")
    if package:
        try:
            description = json.loads(package).get("description")
            if isinstance(description, str) and description.strip():
                return description.strip()[:500]
        except json.JSONDecodeError:
            pass
    for name in ("README.md", "README.rst", "README.txt", "PROJECT.md"):
        for line in files.get(name, "").splitlines():
            candidate = line.strip().lstrip("#").strip()
            if candidate:
                return candidate[:500]
    return f"{project_name} project; purpose requires review."


async def onboard_project(
    session: AsyncSession,
    project_id: str,
    trusted_root: str | Path = "/srv/projects",
) -> ProjectOnboardingResult:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Project not found.", 404)
    project_path = resolve_trusted_project_path(project.path, trusted_root)
    files = await asyncio.to_thread(_read_allowed_files, project_path)
    top_level_entries = await asyncio.to_thread(_safe_top_level_entries, project_path)
    git = await asyncio.to_thread(_git_metadata, project_path)
    architecture = _architecture(files)
    current_state = "Repository reviewed from approved top-level project files."
    if git.branch:
        cleanliness = "clean" if git.clean else "dirty"
        current_state += f" Git branch: {git.branch}; working tree: {cleanliness}."

    await update_memory(
        session,
        project_id,
        ProjectMemoryUpdate(
            purpose=_purpose(files, project.name),
            current_state=current_state,
            architecture_summary=", ".join(architecture) or "Not identified from approved files",
            important_decisions=[],
            coding_rules=["Follow repository AGENTS.md instructions"]
            if "AGENTS.md" in files
            else [],
            current_focus="Review the onboarding baseline",
            next_steps=["Confirm project purpose and priorities"],
        ),
    )
    await create_project_event(
        session,
        project_id,
        ProjectEventCreate(
            type=ProjectEventType.MEMORY_UPDATED,
            status=ProjectStatus.IDLE,
            message="Project onboarding baseline created.",
            metadata={"source": "read_only_onboarding"},
        ),
    )
    return ProjectOnboardingResult(
        project=await get_project(session, project_id),
        inspected_files=sorted(files),
        top_level_entries=top_level_entries,
        git=ProjectGitInfo(
            branch=git.branch,
            clean=git.clean,
            latest_commit=git.latest_commit,
        ),
    )
