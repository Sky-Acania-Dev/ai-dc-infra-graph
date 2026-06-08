"""add crews and construction tasks

Revision ID: 1b44a0c7fd2e
Revises: 8c3b91a2f5d4
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1b44a0c7fd2e"
down_revision: Union[str, Sequence[str], None] = "8c3b91a2f5d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personnel",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("employee_uid", sa.Text(), nullable=False),
        sa.Column("user_uid", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("trade", sa.Text(), server_default="", nullable=False),
        sa.Column("company", sa.Text(), server_default="", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.ForeignKeyConstraint(["user_uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "employee_uid", name="uq_personnel_project_employee_uid"),
    )
    op.create_index("ix_personnel_project_active", "personnel", ["project_uid", "active"], unique=False)
    op.create_index("ix_personnel_user", "personnel", ["user_uid"], unique=False)

    op.create_table(
        "crews",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("crew_type", sa.Text(), server_default="", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("project_uid", "name", name="uq_crews_project_name"),
    )
    op.create_index("ix_crews_project_active", "crews", ["project_uid", "active"], unique=False)

    op.create_table(
        "crew_members",
        sa.Column("crew_uid", sa.Text(), nullable=False),
        sa.Column("personnel_uid", sa.Text(), nullable=False),
        sa.Column("role_in_crew", sa.Text(), server_default="member", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role_in_crew in ('lead', 'member', 'foreman')", name="ck_crew_members_role"),
        sa.ForeignKeyConstraint(["crew_uid"], ["crews.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["personnel_uid"], ["personnel.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("crew_uid", "personnel_uid"),
    )
    op.create_index("ix_crew_members_personnel", "crew_members", ["personnel_uid", "active"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("uid", sa.Text(), nullable=False),
        sa.Column("project_uid", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("priority", sa.Text(), server_default="normal", nullable=False),
        sa.Column("created_by_user_uid", sa.Text(), nullable=True),
        sa.Column("assigned_crew_uid", sa.Text(), nullable=True),
        sa.Column("assigned_personnel_uid", sa.Text(), nullable=True),
        sa.Column("submitted_by_personnel_uid", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_uid", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.Text(), server_default="cable", nullable=False),
        sa.Column("entity_filter_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("target_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("submission_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("review_note", sa.Text(), server_default="", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "task_type in ('cable_pull', 'cable_dress', 'cable_termination', 'cable_test', 'cable_label', 'cable_rework', 'inspection')",
            name="ck_tasks_task_type",
        ),
        sa.CheckConstraint(
            "status in ('draft', 'assigned', 'in_progress', 'submitted', 'approved', 'denied', 'cancelled')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint("priority in ('low', 'normal', 'high', 'urgent')", name="ck_tasks_priority"),
        sa.CheckConstraint("entity_type in ('cable', 'cabinet', 'device', 'port', 'bundle')", name="ck_tasks_entity_type"),
        sa.ForeignKeyConstraint(["assigned_crew_uid"], ["crews.uid"]),
        sa.ForeignKeyConstraint(["assigned_personnel_uid"], ["personnel.uid"]),
        sa.ForeignKeyConstraint(["created_by_user_uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["project_uid"], ["projects.uid"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["submitted_by_personnel_uid"], ["personnel.uid"]),
        sa.PrimaryKeyConstraint("uid"),
    )
    op.create_index("ix_tasks_assigned_crew", "tasks", ["assigned_crew_uid", "status"], unique=False)
    op.create_index("ix_tasks_assigned_personnel", "tasks", ["assigned_personnel_uid", "status"], unique=False)
    op.create_index("ix_tasks_project_status", "tasks", ["project_uid", "status", "created_at"], unique=False)
    op.create_index("ix_tasks_review_queue", "tasks", ["project_uid", "status", "submitted_at"], unique=False)

    op.create_table(
        "task_entities",
        sa.Column("task_uid", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_uid", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_uid"], ["tasks.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_uid", "entity_type", "entity_uid"),
    )
    op.create_index("ix_task_entities_entity", "task_entities", ["entity_type", "entity_uid"], unique=False)

    op.create_table(
        "task_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_uid", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_user_uid", sa.Text(), nullable=True),
        sa.Column("actor_personnel_uid", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "event_type in ('created', 'assigned', 'started', 'submitted', 'approved', 'denied', 'cancelled', 'applied')",
            name="ck_task_events_type",
        ),
        sa.ForeignKeyConstraint(["actor_personnel_uid"], ["personnel.uid"]),
        sa.ForeignKeyConstraint(["actor_user_uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["task_uid"], ["tasks.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_events_actor", "task_events", ["actor_user_uid", "created_at"], unique=False)
    op.create_index("ix_task_events_task_created", "task_events", ["task_uid", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_events_task_created", table_name="task_events")
    op.drop_index("ix_task_events_actor", table_name="task_events")
    op.drop_table("task_events")
    op.drop_index("ix_task_entities_entity", table_name="task_entities")
    op.drop_table("task_entities")
    op.drop_index("ix_tasks_review_queue", table_name="tasks")
    op.drop_index("ix_tasks_project_status", table_name="tasks")
    op.drop_index("ix_tasks_assigned_personnel", table_name="tasks")
    op.drop_index("ix_tasks_assigned_crew", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_crew_members_personnel", table_name="crew_members")
    op.drop_table("crew_members")
    op.drop_index("ix_crews_project_active", table_name="crews")
    op.drop_table("crews")
    op.drop_index("ix_personnel_user", table_name="personnel")
    op.drop_index("ix_personnel_project_active", table_name="personnel")
    op.drop_table("personnel")
