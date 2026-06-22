"""add cable change orders

Revision ID: e41f9c3d2a77
Revises: c24f6d71b8a2, d2a7f4c9e8b1
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e41f9c3d2a77"
down_revision: str | Sequence[str] | None = ("c24f6d71b8a2", "d2a7f4c9e8b1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cables", sa.Column("a_label_text", sa.Text(), server_default="", nullable=False))
    op.add_column("cables", sa.Column("z_label_text", sa.Text(), server_default="", nullable=False))

    op.drop_constraint("ck_tasks_task_type", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_task_type",
        "tasks",
        "task_type in ('cable_pull', 'cable_dress', 'cable_termination', 'cable_test', 'cable_label', 'cable_rework', 'cable_retirement', 'cable_removal', 'inspection')",
    )
    op.drop_constraint("ck_tasks_status", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_status",
        "tasks",
        "status in ('draft', 'assigned', 'in_progress', 'submitted', 'approved', 'denied', 'cancelled', 'abandoned', 'superseded')",
    )
    op.drop_constraint("ck_task_events_type", "task_events", type_="check")
    op.create_check_constraint(
        "ck_task_events_type",
        "task_events",
        "event_type in ('created', 'assigned', 'started', 'submitted', 'approved', 'denied', 'cancelled', 'abandoned', 'superseded', 'applied')",
    )

    op.create_table(
        "change_orders",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("change_order_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("source_type", sa.Text(), server_default="", nullable=False),
        sa.Column("source_uid", sa.Text(), server_default="", nullable=False),
        sa.Column("requested_by_user_uid", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_uid", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("items_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('draft', 'resolved', 'review_ready', 'approved', 'executing', 'partially_complete', 'complete', 'rejected', 'cancelled', 'blocked', 'superseded')",
            name="ck_change_orders_status",
        ),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.ForeignKeyConstraint(["requested_by_user_uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "change_order_number", name="uq_change_orders_project_number"),
    )
    op.create_index("ix_change_orders_project_status", "change_orders", ["project_uid", "status", "created_at"])
    op.create_index("ix_change_orders_source", "change_orders", ["source_type", "source_uid"])

    op.create_table(
        "change_order_items",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("change_order_uid", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entity_type", sa.Text(), server_default="cable", nullable=False),
        sa.Column("entity_uid", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("old_entity_uid", sa.Text(), nullable=True),
        sa.Column("new_entity_uid", sa.Text(), nullable=True),
        sa.Column("before_definition", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("after_definition", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("task_plan", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("entity_type in ('cable')", name="ck_change_order_items_entity_type"),
        sa.ForeignKeyConstraint(["change_order_uid"], ["change_orders.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
    )
    op.create_index("ix_change_order_items_order", "change_order_items", ["change_order_uid", "sequence"])
    op.create_index("ix_change_order_items_entity", "change_order_items", ["entity_type", "entity_uid"])
    op.create_index("ix_change_order_items_status", "change_order_items", ["change_order_uid", "status"])

    op.create_table(
        "change_order_task_links",
        sa.Column("change_order_uid", sa.Text(), nullable=False),
        sa.Column("change_order_item_uid", sa.Text(), nullable=False),
        sa.Column("task_uid", sa.Text(), nullable=False),
        sa.Column("effect_type", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["change_order_uid"], ["change_orders.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_order_item_uid"], ["change_order_items.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_uid"], ["tasks.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("change_order_uid", "change_order_item_uid", "task_uid"),
    )
    op.create_index("ix_change_order_task_links_task", "change_order_task_links", ["task_uid"])
    op.create_index("ix_change_order_task_links_order", "change_order_task_links", ["change_order_uid"])

    op.create_table(
        "change_order_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("change_order_uid", sa.Text(), nullable=False),
        sa.Column("change_order_item_uid", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_user_uid", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["change_order_uid"], ["change_orders.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_order_item_uid"], ["change_order_items.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_change_order_events_order", "change_order_events", ["change_order_uid", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_change_order_events_order", table_name="change_order_events")
    op.drop_table("change_order_events")
    op.drop_index("ix_change_order_task_links_order", table_name="change_order_task_links")
    op.drop_index("ix_change_order_task_links_task", table_name="change_order_task_links")
    op.drop_table("change_order_task_links")
    op.drop_index("ix_change_order_items_status", table_name="change_order_items")
    op.drop_index("ix_change_order_items_entity", table_name="change_order_items")
    op.drop_index("ix_change_order_items_order", table_name="change_order_items")
    op.drop_table("change_order_items")
    op.drop_index("ix_change_orders_source", table_name="change_orders")
    op.drop_index("ix_change_orders_project_status", table_name="change_orders")
    op.drop_table("change_orders")

    op.drop_constraint("ck_task_events_type", "task_events", type_="check")
    op.create_check_constraint(
        "ck_task_events_type",
        "task_events",
        "event_type in ('created', 'assigned', 'started', 'submitted', 'approved', 'denied', 'cancelled', 'applied')",
    )
    op.drop_constraint("ck_tasks_status", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_status",
        "tasks",
        "status in ('draft', 'assigned', 'in_progress', 'submitted', 'approved', 'denied', 'cancelled')",
    )
    op.drop_constraint("ck_tasks_task_type", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_task_type",
        "tasks",
        "task_type in ('cable_pull', 'cable_dress', 'cable_termination', 'cable_test', 'cable_label', 'cable_rework', 'inspection')",
    )
    op.drop_column("cables", "z_label_text")
    op.drop_column("cables", "a_label_text")
