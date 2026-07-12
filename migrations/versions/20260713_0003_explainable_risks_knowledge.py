"""Add explainable risks and versioned knowledge documents.

Revision ID: 20260713_0003
Revises: 20260710_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20260713_0003"
down_revision = "20260710_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("jurisdiction", sa.String(120)),
        sa.Column("issuing_authority", sa.String(255)),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True)),
        sa.Column("expiry_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("article_number", sa.String(120)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_status", "knowledge_documents", ["status"])
    op.create_table(
        "risk_findings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.id")),
        sa.Column("review_task_id", sa.String(64), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("contract_text", sa.Text, nullable=False),
        sa.Column("normalized_text", sa.Text, nullable=False),
        sa.Column("location", sa.JSON, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("legal_basis", sa.JSON, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("suggested_revision", sa.Text),
        sa.Column("requires_human_review", sa.Boolean, nullable=False),
        sa.Column("agent_name", sa.String(100)),
        sa.Column("rule_id", sa.String(64)),
        sa.Column("knowledge_document_ids", sa.JSON, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewer_comment", sa.Text),
        sa.Column("ai_original_recommendation", sa.Text),
        sa.Column("human_final_opinion", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_risk_review_task", "risk_findings", ["review_task_id"])
    op.create_index("ix_risk_status", "risk_findings", ["status"])


def downgrade() -> None:
    op.drop_table("risk_findings")
    op.drop_table("knowledge_documents")
