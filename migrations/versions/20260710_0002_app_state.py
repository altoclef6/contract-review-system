"""Add PostgreSQL compatibility document state.

Revision ID: 20260710_0002
Revises: 20260710_0001
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "20260710_0002"
down_revision = "20260710_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "app_state" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_state")),
    )


def downgrade() -> None:
    if "app_state" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("app_state")
