"""Add optional cited map locations without guessing points for existing records.

Revision ID: 0003_map_locations
Revises: 0002_ingestion_provenance
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_map_locations"
down_revision = "0002_ingestion_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("threat_events", sa.Column("map_location", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("threat_events", "map_location")
