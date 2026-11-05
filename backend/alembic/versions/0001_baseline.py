"""Anchor the migration history without creating any business tables.

Revision ID: 0001_baseline
Revises: None
"""
from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Only Alembic's own version table is needed in this phase."""


def downgrade() -> None:
    """There are no business objects to remove."""
