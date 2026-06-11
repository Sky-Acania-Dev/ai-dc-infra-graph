"""add task apply and operation grouping

Revision ID: 6fd79c3a2a11
Revises: 1b44a0c7fd2e
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "6fd79c3a2a11"
down_revision: str | Sequence[str] | None = "1b44a0c7fd2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("applied_by_user_uid", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("tasks_applied_by_user_uid_fkey", "tasks", "users", ["applied_by_user_uid"], ["uid"])

    op.add_column("operation_log", sa.Column("operation_group_uid", sa.Text(), nullable=True))
    op.add_column("operation_log", sa.Column("source_type", sa.Text(), nullable=True))
    op.add_column("operation_log", sa.Column("source_uid", sa.Text(), nullable=True))
    op.create_index("ix_operation_log_group", "operation_log", ["operation_group_uid", "id"], unique=False)
    op.create_index("ix_operation_log_source", "operation_log", ["source_type", "source_uid", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_operation_log_source", table_name="operation_log")
    op.drop_index("ix_operation_log_group", table_name="operation_log")
    op.drop_column("operation_log", "source_uid")
    op.drop_column("operation_log", "source_type")
    op.drop_column("operation_log", "operation_group_uid")

    op.drop_constraint("tasks_applied_by_user_uid_fkey", "tasks", type_="foreignkey")
    op.drop_column("tasks", "applied_at")
    op.drop_column("tasks", "applied_by_user_uid")
