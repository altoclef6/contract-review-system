"""Add immutable contract version lineage and hashes.

Revision ID: 20260713_0004
Revises: 20260713_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "20260713_0004"
down_revision = "20260713_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("contract_versions") as batch_op:
        batch_op.add_column(sa.Column("file_hash", sa.String(64)))
        batch_op.add_column(
            sa.Column(
                "parent_version_id",
                sa.String(64),
                sa.ForeignKey("contract_versions.id"),
            )
        )
        batch_op.add_column(
            sa.Column("version_type", sa.String(30), nullable=False, server_default="original")
        )
        batch_op.create_index("ix_contract_versions_file_hash", ["file_hash"])
        batch_op.create_index(
            "ix_contract_versions_parent_version_id", ["parent_version_id"]
        )
        batch_op.create_index("ix_contract_versions_version_type", ["version_type"])


def downgrade() -> None:
    with op.batch_alter_table("contract_versions") as batch_op:
        batch_op.drop_index("ix_contract_versions_version_type")
        batch_op.drop_index("ix_contract_versions_parent_version_id")
        batch_op.drop_index("ix_contract_versions_file_hash")
        batch_op.drop_column("version_type")
        batch_op.drop_column("parent_version_id")
        batch_op.drop_column("file_hash")
