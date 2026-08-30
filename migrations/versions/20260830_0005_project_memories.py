"""Add concise per-project memory.

Revision ID: 20260830_0005
Revises: 20260830_0004
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0005"
down_revision: str | None = "20260830_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    memories = op.create_table(
        "project_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("current_state", sa.Text(), nullable=False),
        sa.Column("architecture_summary", sa.Text(), nullable=False),
        sa.Column("important_decisions", sa.JSON(), nullable=False),
        sa.Column("coding_rules", sa.JSON(), nullable=False),
        sa.Column("current_focus", sa.Text(), nullable=False),
        sa.Column("next_steps", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_project_memories_project_id"),
    )
    op.create_index("ix_project_memories_project_id", "project_memories", ["project_id"])
    op.bulk_insert(
        memories,
        [
            {
                "id": "4ff67a8e-6550-4ac6-b0f8-166272301a24",
                "project_id": "ai-playground",
                "purpose": "A personal AI control room for managing registered software projects.",
                "current_state": "Work history and live Codex execution are operational.",
                "architecture_summary": "React, FastAPI, PostgreSQL, SSE, and sandboxed Codex.",
                "important_decisions": [
                    "PostgreSQL is the source of truth.",
                    "Only registered project paths may be executed.",
                    "Keep research as concise briefs rather than raw conversations.",
                ],
                "coding_rules": [
                    "Create a project task before meaningful build work.",
                    "Keep route handlers thin and business logic in services.",
                    "Do not expose secrets or disable Codex sandboxing.",
                ],
                "current_focus": "Keep project context isolated, lightweight, and reliable.",
                "next_steps": [
                    "Use concise project context when generating future coding prompts."
                ],
            },
            {
                "id": "898190a3-8379-4775-b247-304513b4e32d",
                "project_id": "office-project",
                "purpose": "An independent office application registered with AI Playground.",
                "current_state": "The separate repository is visible from the control room.",
                "architecture_summary": "Implementation remains in /srv/projects/project-two-web.",
                "important_decisions": [
                    "Keep Office Project code and history separate from AI Playground."
                ],
                "coding_rules": [
                    "Follow repository requirements and preserve working functionality."
                ],
                "current_focus": "No work is currently active.",
                "next_steps": [],
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_project_memories_project_id", table_name="project_memories")
    op.drop_table("project_memories")
