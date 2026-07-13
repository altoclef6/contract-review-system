"""Add optional contract counterparty and commercial fields.

Revision ID: 20260713_0005
Revises: 20260713_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260713_0005"
down_revision = "20260713_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("counterparty", sa.String(255), nullable=True))
    op.add_column("contracts", sa.Column("amount", sa.Numeric(18, 2), nullable=True))
    op.add_column(
        "contracts",
        sa.Column("currency", sa.String(3), nullable=True, server_default="CNY"),
    )


def downgrade() -> None:
    op.drop_column("contracts", "currency")
    op.drop_column("contracts", "amount")
    op.drop_column("contracts", "counterparty")
