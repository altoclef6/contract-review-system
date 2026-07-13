"""Create the immutable baseline enterprise schema snapshot.

Revision ID: 20260710_0001
Revises:
Create Date: 2026-07-10

This migration intentionally declares its original tables instead of calling
current ``Base.metadata.create_all``. Otherwise later model additions are
created too early and incremental migrations fail on a fresh database.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260710_0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "contracts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("creator_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    for column in ("title", "category", "status", "creator_id"):
        op.create_index(f"ix_contracts_{column}", "contracts", [column])

    op.create_table(
        "contract_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("content_type", sa.String(120)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("text_content", sa.Text()),
        sa.Column("created_by", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("contract_id", "version", name="uq_contract_versions_contract_id_version"),
    )
    op.create_index("ix_contract_versions_contract_id", "contract_versions", ["contract_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.id")),
        sa.Column("contract_version_id", sa.String(64), sa.ForeignKey("contract_versions.id")),
        sa.Column("creator_id", sa.String(64), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("model_provider", sa.String(50)),
        sa.Column("model_name", sa.String(120)),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("token_usage", sa.Integer()),
        sa.Column("risk_score", sa.Float()),
        sa.Column("risk_level", sa.String(30)),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        *_timestamps(),
    )
    for column in ("contract_id", "creator_id", "status", "risk_level"):
        op.create_index(f"ix_reviews_{column}", "reviews", [column])

    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("api_key_cipher", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(500)),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_model_configs_is_active", "model_configs", ["is_active"])

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("contract_type", sa.String(30), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_prompt_templates_contract_type", "prompt_templates", ["contract_type"])
    op.create_index("ix_prompt_templates_stage", "prompt_templates", ["stage"])

    op.create_table(
        "workflows",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_step", sa.String(30), nullable=False),
        sa.Column("submitted_by", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("legal_reviewer_id", sa.String(64), sa.ForeignKey("users.id")),
        sa.Column("manager_reviewer_id", sa.String(64), sa.ForeignKey("users.id")),
        sa.Column("history", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    for column in ("contract_id", "status", "current_step"):
        op.create_index(f"ix_workflows_{column}", "workflows", [column])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    for column in ("user_id", "type", "is_read"):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(64)),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target", sa.String(255)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("actor_id", "action", "created_at"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])


def downgrade() -> None:
    for table in (
        "audit_logs",
        "notifications",
        "workflows",
        "prompt_templates",
        "model_configs",
        "reviews",
        "contract_versions",
        "contracts",
        "users",
    ):
        op.drop_table(table)
