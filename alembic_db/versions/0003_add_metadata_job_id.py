"""
Add system_metadata and job_id columns to asset_references.
Change preview_id FK from assets.id to asset_references.id.

Revision ID: 0003_add_metadata_job_id
Revises: 0002_merge_to_asset_references
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

from app.database.models import NAMING_CONVENTION

revision = "0003_add_metadata_job_id"
down_revision = "0002_merge_to_asset_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("asset_references") as batch_op:
        batch_op.add_column(
            sa.Column("system_metadata", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("job_id", sa.String(length=36), nullable=True)
        )

    # Change preview_id FK from assets.id to asset_references.id (self-ref).
    # Existing values are asset-content IDs that won't match reference IDs,
    # so null them out first.
    op.execute("UPDATE asset_references SET preview_id = NULL WHERE preview_id IS NOT NULL")
    with op.batch_alter_table(
        "asset_references", naming_convention=NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_asset_references_preview_id_assets", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_asset_references_preview_id_asset_references",
            "asset_references",
            ["preview_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "asset_references", naming_convention=NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_asset_references_preview_id_asset_references", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_asset_references_preview_id_assets",
            "assets",
            ["preview_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("asset_references") as batch_op:
        batch_op.drop_column("job_id")
        batch_op.drop_column("system_metadata")
