"""Create project status and event tables.

Revision ID: 20260829_0001
Revises:
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_task", sa.Text(), nullable=True),
        sa.Column("last_completed_task", sa.Text(), nullable=True),
        sa.Column("active_agent", sa.String(length=160), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recent_files", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("checks", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.CheckConstraint(
            "status IN ('IDLE', 'RUNNING', 'DONE', 'FAILED')", name="ck_projects_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    op.create_table(
        "project_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("agent", sa.String(length=160), nullable=True),
        sa.Column("file", sa.String(length=500), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_project_events_project_id", "project_events", ["project_id"])
    op.create_index(
        "ix_project_events_project_timestamp", "project_events", ["project_id", "timestamp"]
    )


def downgrade() -> None:
    op.drop_index("ix_project_events_project_timestamp", table_name="project_events")
    op.drop_index("ix_project_events_project_id", table_name="project_events")
    op.drop_table("project_events")
    op.drop_table("projects")
