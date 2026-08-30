"""Backfill meaningful AI Playground project task history.

Revision ID: 20260830_0004
Revises: 20260829_0003
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260830_0004"
down_revision: str | None = "20260829_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_IDS = (
    "0d897996-f98e-4b99-8b2f-3f0bf5935c9f",
    "4cc6e241-afba-4d93-898c-5b0db6905240",
    "b48fe155-dad8-4ad1-b876-fe41c80a633a",
    "0245c755-07b0-482a-84ce-02c5e4d588bd",
    "bfa61ea0-8fc7-49b7-ac97-c58dc89064c2",
    "89cc72ed-b488-4dc3-b06e-6200939879c7",
)


def upgrade() -> None:
    # These rows summarize known human-level milestones. Raw events stay untouched and
    # are deliberately not converted one-for-one into noisy duplicate tasks.
    op.execute(
        """
        INSERT INTO project_tasks (
            id, project_id, title, description, prompt, status, agent,
            result_summary, created_at, started_at, completed_at, updated_at
        )
        SELECT
            history.id,
            'ai-playground',
            history.title,
            history.description,
            NULL,
            'DONE',
            'Codex',
            history.result_summary,
            history.completed_at,
            history.completed_at,
            history.completed_at,
            history.completed_at
        FROM (
            VALUES
                (
                    '0d897996-f98e-4b99-8b2f-3f0bf5935c9f',
                    'Connect AI assistant backend to OpenAI',
                    'Built the FastAPI assistant backend and connected it to OpenAI.',
                    'The AI assistant backend can send prompts to OpenAI and return responses.',
                    TIMESTAMPTZ '2026-08-27 10:30:00+00'
                ),
                (
                    '4cc6e241-afba-4d93-898c-5b0db6905240',
                    'Connect the frontend chat to the backend',
                    'Connected React chat to FastAPI with loading and error handling.',
                    'Chat messages now reach the backend and display assistant replies.',
                    TIMESTAMPTZ '2026-08-29 03:50:00+00'
                ),
                (
                    'b48fe155-dad8-4ad1-b876-fe41c80a633a',
                    'Build the terminal project dashboard',
                    'Built a terminal dashboard for both registered projects.',
                    'A reusable terminal dashboard now shows project status and activity.',
                    TIMESTAMPTZ '2026-08-29 12:20:00+00'
                ),
                (
                    '0245c755-07b0-482a-84ce-02c5e4d588bd',
                    'Add PostgreSQL project status and live updates',
                    'Connected the dashboard to PostgreSQL and Server-Sent Events.',
                    'Project status persists in PostgreSQL and updates live without refreshing.',
                    TIMESTAMPTZ '2026-08-29 12:31:19.180847+00'
                ),
                (
                    'bfa61ea0-8fc7-49b7-ac97-c58dc89064c2',
                    'Add Research / Build Briefs',
                    'Added concise project briefs linked to projects and optional build tasks.',
                    'Research decisions and build prompts are stored as concise reusable briefs.',
                    TIMESTAMPTZ '2026-08-29 14:12:28.014033+00'
                ),
                (
                    '89cc72ed-b488-4dc3-b06e-6200939879c7',
                    'Simplify the dashboard for human-readable project status',
                    'Moved technical detail behind a collapsed, human-friendly overview.',
                    'The default dashboard now presents project work in clear human language.',
                    TIMESTAMPTZ '2026-08-30 00:30:00+00'
                )
        ) AS history(id, title, description, result_summary, completed_at)
        WHERE EXISTS (
            SELECT 1 FROM projects WHERE projects.id = 'ai-playground'
        )
        AND NOT EXISTS (
            SELECT 1
            FROM project_tasks existing
            WHERE existing.id = history.id
               OR (
                    existing.project_id = 'ai-playground'
                    AND existing.title = history.title
               )
        )
        """
    )


def downgrade() -> None:
    ids = ", ".join(f"'{task_id}'" for task_id in _BACKFILL_IDS)
    op.execute(f"DELETE FROM project_tasks WHERE id IN ({ids})")
