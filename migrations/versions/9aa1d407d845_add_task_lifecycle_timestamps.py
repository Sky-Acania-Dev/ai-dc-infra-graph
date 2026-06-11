"""add task lifecycle timestamps

Revision ID: 9aa1d407d845
Revises: 6fd79c3a2a11
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "9aa1d407d845"
down_revision: str | Sequence[str] | None = "6fd79c3a2a11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "cancelled_at")
    op.drop_column("tasks", "started_at")
