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
    op.add_column("contract_versions", sa.Column("file_hash", sa.String(64)))
    op.add_column(
        "contract_versions",
        sa.Column("parent_version_id", sa.String(64), sa.ForeignKey("contract_versions.id")),
    )
    op.add_column(
        "contract_versions",
        sa.Column("version_type", sa.String(30), nullable=False, server_default="original"),
    )
    op.create_index("ix_contract_versions_file_hash", "contract_versions", ["file_hash"])
    op.create_index(
        "ix_contract_versions_parent_version_id", "contract_versions", ["parent_version_id"]
    )
    op.create_index("ix_contract_versions_version_type", "contract_versions", ["version_type"])


def downgrade() -> None:
    op.drop_index("ix_contract_versions_version_type", table_name="contract_versions")
    op.drop_index("ix_contract_versions_parent_version_id", table_name="contract_versions")
    op.drop_index("ix_contract_versions_file_hash", table_name="contract_versions")
    op.drop_column("contract_versions", "version_type")
    op.drop_column("contract_versions", "parent_version_id")
    op.drop_column("contract_versions", "file_hash")
