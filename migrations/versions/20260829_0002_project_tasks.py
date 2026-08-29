"""Create project tasks and connect events to tasks.

Revision ID: 20260829_0002
Revises: 20260829_0001
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("agent", sa.String(length=160), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_project_tasks_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"])
    op.add_column("project_events", sa.Column("task_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_project_events_task_id",
        "project_events",
        "project_tasks",
        ["task_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_project_events_task_id", "project_events", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_project_events_task_id", table_name="project_events")
    op.drop_constraint("fk_project_events_task_id", "project_events", type_="foreignkey")
    op.drop_column("project_events", "task_id")
    op.drop_index("ix_project_tasks_project_id", table_name="project_tasks")
    op.drop_table("project_tasks")
