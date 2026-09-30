"""initial threat tables

Revision ID: 0001_initial_threat_tables
Revises:
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_threat_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_items",
        sa.Column("id", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_name", sa.String(length=240), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("reliability_tier", sa.String(length=80), nullable=False),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_official", sa.Boolean(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_items_source_type", "source_items", ["source_type"])

    op.create_table(
        "threat_events",
        sa.Column("id", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("geography", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_uncertainties", sa.JSON(), nullable=False),
        sa.Column("contradictory_evidence", sa.JSON(), nullable=False),
        sa.Column("next_watch_items", sa.JSON(), nullable=False),
        sa.Column("implications", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threat_events_category", "threat_events", ["category"])
    op.create_index("ix_threat_events_status", "threat_events", ["status"])
    op.create_index("ix_threat_events_updated_at", "threat_events", ["updated_at"])

    op.create_table(
        "threat_scores",
        sa.Column("threat_id", sa.String(length=160), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("credibility", sa.Float(), nullable=False),
        sa.Column("velocity", sa.Float(), nullable=False),
        sa.Column("exposure", sa.Float(), nullable=False),
        sa.Column("uncertainty_penalty", sa.Float(), nullable=False),
        sa.Column("priority", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=30), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["threat_id"], ["threat_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("threat_id"),
    )
    op.create_index("ix_threat_scores_priority", "threat_scores", ["priority"])

    op.create_table(
        "threat_sources",
        sa.Column("threat_id", sa.String(length=160), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["threat_id"], ["threat_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("threat_id", "source_id"),
    )

    op.create_table(
        "extracted_claims",
        sa.Column("id", sa.String(length=160), nullable=False),
        sa.Column("threat_id", sa.String(length=160), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("support_level", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_material", sa.Boolean(), nullable=False),
        sa.Column("contradicts_claim_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["threat_id"], ["threat_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "threat_timeline_entries",
        sa.Column("id", sa.String(length=160), nullable=False),
        sa.Column("threat_id", sa.String(length=160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("material_change", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["threat_id"], ["threat_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threat_timeline_entries_occurred_at", "threat_timeline_entries", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_threat_timeline_entries_occurred_at", table_name="threat_timeline_entries")
    op.drop_table("threat_timeline_entries")
    op.drop_table("extracted_claims")
    op.drop_table("threat_sources")
    op.drop_index("ix_threat_scores_priority", table_name="threat_scores")
    op.drop_table("threat_scores")
    op.drop_index("ix_threat_events_updated_at", table_name="threat_events")
    op.drop_index("ix_threat_events_status", table_name="threat_events")
    op.drop_index("ix_threat_events_category", table_name="threat_events")
    op.drop_table("threat_events")
    op.drop_index("ix_source_items_source_type", table_name="source_items")
    op.drop_table("source_items")
