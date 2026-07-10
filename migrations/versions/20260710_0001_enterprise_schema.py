"""Create enterprise contract review schema.

Revision ID: 20260710_0001
Revises:
Create Date: 2026-07-10
"""

from alembic import op

from contract_review.database import models  # noqa: F401
from contract_review.database.base import Base

revision = "20260710_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
