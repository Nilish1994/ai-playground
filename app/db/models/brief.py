from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.task import ProjectTask


class ProjectBrief(Base):
    __tablename__ = "project_briefs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'READY', 'BUILDING', 'DONE')",
            name="ck_project_briefs_status",
        ),
        Index("ix_project_briefs_project_updated", "project_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    decisions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    build_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="briefs")
    task: Mapped[ProjectTask | None] = relationship(back_populates="briefs")
