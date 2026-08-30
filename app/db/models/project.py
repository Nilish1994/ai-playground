from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.brief import ProjectBrief
    from app.db.models.memory import ProjectMemory
    from app.db.models.task import ProjectTask


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IDLE', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_projects_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="IDLE")
    current_task: Mapped[str | None] = mapped_column(Text)
    last_completed_task: Mapped[str | None] = mapped_column(Text)
    active_agent: Mapped[str | None] = mapped_column(String(160))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    recent_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    tasks: Mapped[list[ProjectTask]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    briefs: Mapped[list[ProjectBrief]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    memory: Mapped[ProjectMemory | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    events: Mapped[list[ProjectEvent]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectEvent(Base):
    __tablename__ = "project_events"
    __table_args__ = (Index("ix_project_events_project_timestamp", "project_id", "timestamp"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    agent: Mapped[str | None] = mapped_column(String(160))
    file: Mapped[str | None] = mapped_column(String(500))
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    project: Mapped[Project] = relationship(back_populates="events")
    task: Mapped[ProjectTask | None] = relationship(back_populates="events")
