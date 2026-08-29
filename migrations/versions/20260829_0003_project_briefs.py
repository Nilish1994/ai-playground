"""Create project research and build briefs.

Revision ID: 20260829_0003
Revises: 20260829_0002
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0003"
down_revision: str | None = "20260829_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_briefs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("build_prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'READY', 'BUILDING', 'DONE')",
            name="ck_project_briefs_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["project_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_briefs_project_id", "project_briefs", ["project_id"])
    op.create_index("ix_project_briefs_task_id", "project_briefs", ["task_id"])
    op.create_index(
        "ix_project_briefs_project_updated",
        "project_briefs",
        ["project_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_briefs_project_updated", table_name="project_briefs")
    op.drop_index("ix_project_briefs_task_id", table_name="project_briefs")
    op.drop_index("ix_project_briefs_project_id", table_name="project_briefs")
    op.drop_table("project_briefs")
