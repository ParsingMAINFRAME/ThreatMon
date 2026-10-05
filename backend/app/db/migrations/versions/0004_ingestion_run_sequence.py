"""Record ingestion run order explicitly so tied timestamps cannot reorder runs.

Existing runs keep sequence 0 and remain ordered among themselves by their timestamps.

Revision ID: 0004_ingestion_run_sequence
Revises: 0003_map_locations
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_ingestion_run_sequence"
down_revision = "0003_map_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_ingestion_runs_sequence", "ingestion_runs", ["sequence"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_sequence", table_name="ingestion_runs")
    with op.batch_alter_table("ingestion_runs") as batch:
        batch.drop_column("sequence")
