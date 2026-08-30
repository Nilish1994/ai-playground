from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.project import Project


class ProjectMemory(Base):
    __tablename__ = "project_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    architecture_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    important_decisions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    coding_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    current_focus: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="memory")
