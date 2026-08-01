"""Add enterprise tenancy, organization and persistent agent execution tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260729_0008"
down_revision = "20260713_0007"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}:
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(80), nullable=False, unique=True),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("settings", sa.JSON(), nullable=False),
            *_timestamps(),
        )
        op.create_index("ix_companies_name", "companies", ["name"])
        op.create_index("ix_companies_code", "companies", ["code"], unique=True)
        op.create_index("ix_companies_status", "companies", ["status"])
    if not inspector.has_table("departments"):
        op.create_table(
            "departments",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "company_id",
                sa.String(64),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "parent_id",
                sa.String(64),
                sa.ForeignKey("departments.id", ondelete="SET NULL"),
            ),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("code", sa.String(80)),
            sa.Column("status", sa.String(30), nullable=False),
            *_timestamps(),
            sa.UniqueConstraint("company_id", "name"),
        )
        for column in ("company_id", "parent_id", "code", "status"):
            op.create_index(f"ix_departments_{column}", "departments", [column])

    _add_column("users", sa.Column("company_id", sa.String(64), nullable=True))
    _add_column("users", sa.Column("department_id", sa.String(64), nullable=True))
    _add_column("users", sa.Column("job_title", sa.String(120), nullable=True))
    _add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )
    for table in (
        "contracts",
        "reviews",
        "review_tasks",
        "model_configs",
        "prompt_templates",
        "workflows",
        "risk_findings",
        "knowledge_documents",
    ):
        if inspector.has_table(table):
            _add_column(table, sa.Column("company_id", sa.String(64), nullable=True))

    for name, type_ in (
        ("company_id", sa.String(64)),
        ("resource_type", sa.String(80)),
        ("resource_id", sa.String(64)),
        ("request_id", sa.String(80)),
        ("ip_address", sa.String(80)),
        ("user_agent", sa.String(500)),
    ):
        _add_column("audit_logs", sa.Column(name, type_, nullable=True))
    _add_column(
        "audit_logs",
        sa.Column("result", sa.String(30), nullable=False, server_default="success"),
    )

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("contract_id", sa.String(64)),
        sa.Column("task_type", sa.String(80), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("safe_error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    for column in ("company_id", "created_by", "contract_id", "task_type", "status"):
        op.create_index(f"ix_agent_tasks_{column}", "agent_tasks", [column])
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(64),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("task_id", "sequence"),
    )
    op.create_index("ix_agent_steps_task_id", "agent_steps", ["task_id"])
    op.create_index("ix_agent_steps_status", "agent_steps", ["status"])
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(64),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.String(64),
            sa.ForeignKey("agent_steps.id", ondelete="SET NULL"),
        ),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(120), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("confirmed_by", sa.String(64)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    for column in ("task_id", "step_id", "company_id", "tool_name", "risk_level", "status"):
        op.create_index(f"ix_agent_tool_calls_{column}", "agent_tool_calls", [column])
    op.create_table(
        "agent_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(64),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("task_id", "company_id", "event_type", "created_at"):
        op.create_index(f"ix_agent_events_{column}", "agent_events", [column])


def downgrade() -> None:
    for table in ("agent_events", "agent_tool_calls", "agent_steps", "agent_tasks"):
        op.drop_table(table)
    for table in (
        "audit_logs",
        "knowledge_documents",
        "risk_findings",
        "workflows",
        "prompt_templates",
        "model_configs",
        "review_tasks",
        "reviews",
        "contracts",
        "users",
    ):
        existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
        candidates = (
            [
                "company_id",
                "resource_type",
                "resource_id",
                "request_id",
                "ip_address",
                "user_agent",
                "result",
            ]
            if table == "audit_logs"
            else ["company_id", "department_id", "job_title", "token_version"]
            if table == "users"
            else ["company_id"]
        )
        with op.batch_alter_table(table) as batch:
            for column in candidates:
                if column in existing:
                    batch.drop_column(column)
    op.drop_table("departments")
    op.drop_table("companies")
