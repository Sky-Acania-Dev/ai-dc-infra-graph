"""add entity groups

Revision ID: a7c9e2d4f613
Revises: e41f9c3d2a77
Create Date: 2026-06-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a7c9e2d4f613"
down_revision: str | Sequence[str] | None = "e41f9c3d2a77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENTITY_TYPES = "entity_type in ('cable', 'cabinet', 'device', 'port', 'bundle')"


def upgrade() -> None:
    op.create_table(
        "entity_groups",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("entity_type", sa.Text(), server_default="cable", nullable=False),
        sa.Column("owner_user_uid", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(ENTITY_TYPES, name="ck_entity_groups_entity_type"),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.ForeignKeyConstraint(["owner_user_uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "entity_type", "name", name="uq_entity_groups_project_entity_name"),
    )
    op.create_index("ix_entity_groups_project_entity", "entity_groups", ["project_uid", "entity_type", "created_at"])
    op.create_index("ix_entity_groups_owner", "entity_groups", ["owner_user_uid"])

    op.create_table(
        "entity_group_members",
        sa.Column("group_uid", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_uid", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(ENTITY_TYPES, name="ck_entity_group_members_entity_type"),
        sa.ForeignKeyConstraint(["group_uid"], ["entity_groups.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_uid", "entity_type", "entity_uid"),
    )
    op.create_index("ix_entity_group_members_entity", "entity_group_members", ["entity_type", "entity_uid"])


def downgrade() -> None:
    op.drop_index("ix_entity_group_members_entity", table_name="entity_group_members")
    op.drop_table("entity_group_members")
    op.drop_index("ix_entity_groups_owner", table_name="entity_groups")
    op.drop_index("ix_entity_groups_project_entity", table_name="entity_groups")
    op.drop_table("entity_groups")