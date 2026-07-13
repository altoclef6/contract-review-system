"""Extend risk findings for human review workflow.

Revision ID: 20260713_0006
Revises: 20260713_0005
"""

import sqlalchemy as sa
from alembic import op

revision = "20260713_0006"
down_revision = "20260713_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("risk_findings") as batch_op:
        batch_op.drop_constraint("fk_risk_findings_contract_id_contracts", type_="foreignkey")
        batch_op.drop_constraint("fk_risk_findings_review_task_id_reviews", type_="foreignkey")
        batch_op.add_column(sa.Column("source_risk_id", sa.String(64)))
        batch_op.add_column(sa.Column("contract_version_id", sa.String(64)))
        batch_op.add_column(sa.Column("assignee_id", sa.String(64)))
        batch_op.add_column(sa.Column("reviewer_id", sa.String(64)))
        batch_op.add_column(sa.Column("created_by", sa.String(64)))
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("state_history", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("comments", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("ai_involved", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("revised_clause", sa.Text()))
        batch_op.alter_column("confidence", existing_type=sa.Float(), nullable=True)
        batch_op.alter_column("status", existing_type=sa.String(30), server_default="pending_review")
        for column in ("source_risk_id", "contract_version_id", "assignee_id", "reviewer_id", "created_by"):
            batch_op.create_index(f"ix_risk_findings_{column}", [column])
    op.execute(
        "UPDATE risk_findings SET status = CASE status "
        "WHEN 'pending' THEN 'pending_review' "
        "WHEN 'accepted' THEN 'confirmed' "
        "WHEN 'modified' THEN 'remediating' "
        "WHEN 'resolved' THEN 'remediated' "
        "ELSE status END"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE risk_findings SET status = CASE status "
        "WHEN 'pending_review' THEN 'pending' "
        "WHEN 'confirmed' THEN 'accepted' "
        "WHEN 'remediating' THEN 'modified' "
        "WHEN 'remediated' THEN 'resolved' "
        "WHEN 'closed' THEN 'resolved' "
        "ELSE status END"
    )
    with op.batch_alter_table("risk_findings") as batch_op:
        for column in ("created_by", "reviewer_id", "assignee_id", "contract_version_id", "source_risk_id"):
            batch_op.drop_index(f"ix_risk_findings_{column}")
        for column in (
            "revised_clause", "ai_involved", "comments", "state_history", "revision", "resolved_at",
            "confirmed_at", "created_by", "reviewer_id", "assignee_id", "contract_version_id",
            "source_risk_id",
        ):
            batch_op.drop_column(column)
        batch_op.alter_column("confidence", existing_type=sa.Float(), nullable=False)
        batch_op.create_foreign_key(
            "fk_risk_findings_review_task_id_reviews", "reviews", ["review_task_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_risk_findings_contract_id_contracts", "contracts", ["contract_id"], ["id"]
        )
