"""add cross hall cable lookup index

Revision ID: c24f6d71b8a2
Revises: b7e1d4a66f3a
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "c24f6d71b8a2"
down_revision: str | Sequence[str] | None = "b7e1d4a66f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_cables_project_type_a_z_ports",
        "cables",
        ["project_uid", "cable_type", "a_port_uid", "z_port_uid"],
        unique=False,
        postgresql_ops={"a_port_uid": "text_pattern_ops", "z_port_uid": "text_pattern_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_cables_project_type_a_z_ports", table_name="cables")
