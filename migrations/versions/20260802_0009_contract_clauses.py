"""Add structured contract clauses without changing existing contract tables.

Revision ID: 20260802_0009
Revises: 20260802_0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_0009"
down_revision = "20260802_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_clause",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("contract_id", sa.String(64), nullable=False),
        sa.Column("contract_version_id", sa.String(64)),
        sa.Column("clause_no", sa.String(120)),
        sa.Column("clause_title", sa.String(300)),
        sa.Column("clause_type", sa.String(120), nullable=False),
        sa.Column("clause_content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("start_position", sa.Integer(), nullable=False),
        sa.Column("end_position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contract_clause_contract_id", "contract_clause", ["contract_id"])
    op.create_index(
        "ix_contract_clause_contract_version_id",
        "contract_clause",
        ["contract_version_id"],
    )
    op.create_index("ix_contract_clause_clause_no", "contract_clause", ["clause_no"])
    op.create_index("ix_contract_clause_clause_type", "contract_clause", ["clause_type"])
    op.create_index("ix_contract_clause_created_at", "contract_clause", ["created_at"])


def downgrade() -> None:
    op.drop_table("contract_clause")
