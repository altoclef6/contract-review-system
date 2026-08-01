"""Add versioned legal knowledge, risk rules, and review citations.

Revision ID: 20260802_0008
Revises: 20260713_0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_0008"
down_revision = "20260729_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_document",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("issuing_authority", sa.String(255)),
        sa.Column("document_number", sa.String(120)),
        sa.Column("publication_date", sa.Date()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("effect_status", sa.String(40), nullable=False),
        sa.Column("version_number", sa.String(80), nullable=False),
        sa.Column("official_source_url", sa.String(1000)),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("verification_status", sa.String(40), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_legal_document_name", "legal_document", ["name"])
    op.create_index("ix_legal_document_type_status", "legal_document", ["document_type", "effect_status"])

    op.create_table(
        "legal_document_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "legal_document_id",
            sa.String(64),
            sa.ForeignKey("legal_document.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.String(80), nullable=False),
        sa.Column("publication_date", sa.Date()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("effect_status", sa.String(40), nullable=False),
        sa.Column("official_source_url", sa.String(1000)),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("verification_status", sa.String(40), nullable=False),
        sa.Column("change_summary", sa.Text()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_document_id", "version_number"),
    )
    op.create_index("ix_legal_version_document", "legal_document_version", ["legal_document_id"])

    op.create_table(
        "legal_article",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "legal_document_id",
            sa.String(64),
            sa.ForeignKey("legal_document.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_document_version_id",
            sa.String(64),
            sa.ForeignKey("legal_document_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chapter_no", sa.String(80)),
        sa.Column("chapter_name", sa.String(255)),
        sa.Column("article_no", sa.String(120), nullable=False),
        sa.Column("article_no_numeric", sa.Integer()),
        sa.Column("title", sa.String(300)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("legal_topics", sa.JSON(), nullable=False),
        sa.Column("contract_types", sa.JSON(), nullable=False),
        sa.Column("is_effective", sa.Boolean(), nullable=False),
        sa.Column("verification_status", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_document_version_id", "article_no"),
    )
    op.create_index("ix_legal_article_document", "legal_article", ["legal_document_id"])
    op.create_index("ix_legal_article_no", "legal_article", ["article_no"])
    op.create_index("ix_legal_article_effective", "legal_article", ["is_effective", "verification_status"])

    op.create_table(
        "contract_risk_rule",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("rule_code", sa.String(80), nullable=False, unique=True),
        sa.Column("rule_name", sa.String(255), nullable=False),
        sa.Column("contract_types", sa.JSON(), nullable=False),
        sa.Column("clause_type", sa.String(120), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("trigger_condition", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("model_prompt", sa.Text(), nullable=False),
        sa.Column("risk_description", sa.Text(), nullable=False),
        sa.Column("possible_consequence", sa.Text(), nullable=False),
        sa.Column("modification_advice", sa.Text(), nullable=False),
        sa.Column("recommended_clause", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contract_risk_rule_clause", "contract_risk_rule", ["clause_type"])
    op.create_index("ix_contract_risk_rule_enabled", "contract_risk_rule", ["is_enabled"])

    op.create_table(
        "risk_rule_legal_article",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "risk_rule_id",
            sa.String(64),
            sa.ForeignKey("contract_risk_rule.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_article_id",
            sa.String(64),
            sa.ForeignKey("legal_article.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("risk_rule_id", "legal_article_id"),
    )
    op.create_index("ix_rule_article_rule", "risk_rule_legal_article", ["risk_rule_id"])
    op.create_index("ix_rule_article_article", "risk_rule_legal_article", ["legal_article_id"])

    op.create_table(
        "review_issue_legal_article",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "review_issue_id",
            sa.String(64),
            sa.ForeignKey("risk_findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_article_id",
            sa.String(64),
            sa.ForeignKey("legal_article.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("review_id", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_issue_id", "legal_article_id"),
    )
    op.create_index("ix_review_issue_article_issue", "review_issue_legal_article", ["review_issue_id"])
    op.create_index("ix_review_issue_article_review", "review_issue_legal_article", ["review_id"])


def downgrade() -> None:
    op.drop_table("review_issue_legal_article")
    op.drop_table("risk_rule_legal_article")
    op.drop_table("contract_risk_rule")
    op.drop_table("legal_article")
    op.drop_table("legal_document_version")
    op.drop_table("legal_document")
