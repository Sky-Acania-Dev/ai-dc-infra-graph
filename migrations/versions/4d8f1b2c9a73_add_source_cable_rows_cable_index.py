"""add source cable rows cable index

Revision ID: 4d8f1b2c9a73
Revises: f6a2b9c7e3d4
Create Date: 2026-08-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "4d8f1b2c9a73"
down_revision: Union[str, None] = "f6a2b9c7e3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_source_cable_rows_cable", "source_cable_rows", ["cable_uid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_source_cable_rows_cable", table_name="source_cable_rows")
