"""Add source provenance and ingestion run journal.

Revision ID: 0002_ingestion_provenance
Revises: 0001_initial_threat_tables
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_ingestion_provenance"
down_revision = "0001_initial_threat_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_items", sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("connector", sa.String(80), nullable=False),
        sa.Column("data_mode", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_ingestion_runs_connector", "ingestion_runs", ["connector"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_connector", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_column("source_items", "provenance")
