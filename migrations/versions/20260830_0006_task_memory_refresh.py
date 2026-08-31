"""Add task memory refresh controls.

Revision ID: 20260830_0006
Revises: 20260830_0005
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0006"
down_revision: str | None = "20260830_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_tasks",
        sa.Column(
            "updates_memory",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "project_tasks",
        sa.Column("memory_refresh_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_tasks",
        sa.Column("memory_refresh_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_tasks", "memory_refresh_completed_at")
    op.drop_column("project_tasks", "memory_refresh_attempted_at")
    op.drop_column("project_tasks", "updates_memory")
