"""add topology versions and entity history

Revision ID: d2a7f4c9e8b1
Revises: b7e1d4a66f3a
Create Date: 2026-06-18 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d2a7f4c9e8b1"
down_revision: str | Sequence[str] | None = "b7e1d4a66f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("operation_log", sa.Column("source_operator", sa.Text(), nullable=True))
    op.add_column("source_imports", sa.Column("version_name", sa.Text(), server_default="", nullable=False))
    op.add_column("source_imports", sa.Column("version_date", sa.Date(), nullable=True))
    op.add_column("source_imports", sa.Column("source_operator", sa.Text(), server_default="", nullable=False))

    op.create_table(
        "topology_versions",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("version_name", sa.Text(), nullable=False),
        sa.Column("version_date", sa.Date(), nullable=True),
        sa.Column("source_operator", sa.Text(), server_default="", nullable=False),
        sa.Column("source_import_uid", sa.Text(), nullable=True),
        sa.Column("operation_group_uid", sa.Text(), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.ForeignKeyConstraint(["source_import_uid"], ["source_imports.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "version_name", name="uq_topology_versions_project_name"),
    )
    op.create_index("ix_topology_versions_project_date", "topology_versions", ["project_uid", "version_date"], unique=False)
    op.create_index("ix_topology_versions_source_import", "topology_versions", ["source_import_uid"], unique=False)

    op.create_table(
        "entity_history",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_uid", sa.Text(), nullable=False),
        sa.Column("first_version_uid", sa.Text(), nullable=True),
        sa.Column("first_operation_id", sa.BigInteger(), nullable=True),
        sa.Column("last_version_uid", sa.Text(), nullable=True),
        sa.Column("last_operation_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["first_operation_id"], ["operation_log.id"]),
        sa.ForeignKeyConstraint(["first_version_uid"], ["topology_versions.uid"]),
        sa.ForeignKeyConstraint(["last_operation_id"], ["operation_log.id"]),
        sa.ForeignKeyConstraint(["last_version_uid"], ["topology_versions.uid"]),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "entity_type", "entity_uid", name="uq_entity_history_entity"),
    )
    op.create_index("ix_entity_history_entity", "entity_history", ["entity_type", "entity_uid"], unique=False)
    op.create_index("ix_entity_history_first_version", "entity_history", ["first_version_uid"], unique=False)
    op.create_index("ix_entity_history_last_version", "entity_history", ["last_version_uid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_entity_history_last_version", table_name="entity_history")
    op.drop_index("ix_entity_history_first_version", table_name="entity_history")
    op.drop_index("ix_entity_history_entity", table_name="entity_history")
    op.drop_table("entity_history")

    op.drop_index("ix_topology_versions_source_import", table_name="topology_versions")
    op.drop_index("ix_topology_versions_project_date", table_name="topology_versions")
    op.drop_table("topology_versions")

    op.drop_column("source_imports", "source_operator")
    op.drop_column("source_imports", "version_date")
    op.drop_column("source_imports", "version_name")
    op.drop_column("operation_log", "source_operator")
