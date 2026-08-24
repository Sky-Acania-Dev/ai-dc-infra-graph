"""add label extraction configs

Revision ID: f6a2b9c7e3d4
Revises: d2a7f4c9e8b1
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f6a2b9c7e3d4"
down_revision: str | Sequence[str] | None = "a7c9e2d4f613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "label_extraction_configs",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("owner_user_uid", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("pair_scope_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("cable_filter_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("label_fields_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("output_layout_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("validation_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.ForeignKeyConstraint(["owner_user_uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "name", name="uq_label_extraction_configs_project_name"),
    )
    op.create_index("ix_label_extraction_configs_project", "label_extraction_configs", ["project_uid", "created_at"])
    op.create_index("ix_label_extraction_configs_owner", "label_extraction_configs", ["owner_user_uid"])


def downgrade() -> None:
    op.drop_index("ix_label_extraction_configs_owner", table_name="label_extraction_configs")
    op.drop_index("ix_label_extraction_configs_project", table_name="label_extraction_configs")
    op.drop_table("label_extraction_configs")
