"""add cable type lookup index

Revision ID: b7e1d4a66f3a
Revises: 9aa1d407d845
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "b7e1d4a66f3a"
down_revision: str | Sequence[str] | None = "9aa1d407d845"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_cables_project_type", "cables", ["project_uid", "cable_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cables_project_type", table_name="cables")
