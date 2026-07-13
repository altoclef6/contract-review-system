
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260713_0007"
down_revision = "20260713_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("review_tasks"):
        return
    op.create_table(
        "review_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("contract_id", sa.String(length=64), nullable=True),
        sa.Column("contract_version_id", sa.String(length=64), nullable=True),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=60), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=160), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("original_file_name", sa.String(length=260), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("contract_type", sa.String(length=60), nullable=False),
        sa.Column("review_id", sa.String(length=80), nullable=True),
        sa.Column("audit_events", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_tasks")),
    )
    op.create_index(op.f("ix_review_tasks_celery_task_id"), "review_tasks", ["celery_task_id"])
    op.create_index(op.f("ix_review_tasks_contract_id"), "review_tasks", ["contract_id"])
    op.create_index(
        op.f("ix_review_tasks_contract_version_id"), "review_tasks", ["contract_version_id"]
    )
    op.create_index(op.f("ix_review_tasks_current_stage"), "review_tasks", ["current_stage"])
    op.create_index(op.f("ix_review_tasks_idempotency_key"), "review_tasks", ["idempotency_key"])
    op.create_index(op.f("ix_review_tasks_requested_by"), "review_tasks", ["requested_by"])
    op.create_index(op.f("ix_review_tasks_review_id"), "review_tasks", ["review_id"])
    op.create_index(op.f("ix_review_tasks_status"), "review_tasks", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("review_tasks"):
        return
    op.drop_index(op.f("ix_review_tasks_status"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_review_id"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_requested_by"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_idempotency_key"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_current_stage"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_contract_version_id"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_contract_id"), table_name="review_tasks")
    op.drop_index(op.f("ix_review_tasks_celery_task_id"), table_name="review_tasks")
    op.drop_table("review_tasks")
