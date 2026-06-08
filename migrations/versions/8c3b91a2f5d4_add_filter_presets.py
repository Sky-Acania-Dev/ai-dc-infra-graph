"""add filter presets

Revision ID: 8c3b91a2f5d4
Revises: 36296b943ff8
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8c3b91a2f5d4"
down_revision: Union[str, Sequence[str], None] = "36296b943ff8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "filter_presets",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("owner_user_uid", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), server_default="private", nullable=False),
        sa.Column("filter_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("sort_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("column_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("entity_type in ('cabinet', 'device', 'cable', 'port', 'bundle')", name="ck_filter_presets_entity_type"),
        sa.CheckConstraint("visibility in ('private', 'project')", name="ck_filter_presets_visibility"),
        sa.ForeignKeyConstraint(["owner_user_uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.PrimaryKeyConstraint("uid"),
    )
    op.create_index("ix_filter_presets_owner_entity", "filter_presets", ["owner_user_uid", "entity_type"], unique=False)
    op.create_index("ix_filter_presets_project_entity", "filter_presets", ["project_uid", "entity_type", "visibility"], unique=False)
    op.create_index(
        "uq_filter_presets_private_owner_name",
        "filter_presets",
        ["project_uid", "owner_user_uid", "entity_type", "name"],
        unique=True,
        postgresql_where=sa.text("owner_user_uid IS NOT NULL"),
    )
    op.create_index(
        "uq_filter_presets_project_name",
        "filter_presets",
        ["project_uid", "entity_type", "name"],
        unique=True,
        postgresql_where=sa.text("owner_user_uid IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_filter_presets_project_name", table_name="filter_presets")
    op.drop_index("uq_filter_presets_private_owner_name", table_name="filter_presets")
    op.drop_index("ix_filter_presets_project_entity", table_name="filter_presets")
    op.drop_index("ix_filter_presets_owner_entity", table_name="filter_presets")
    op.drop_table("filter_presets")
