from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, JSON, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for persistent SQLAlchemy models."""


threat_sources = Table(
    "threat_sources",
    Base.metadata,
    Column("threat_id", ForeignKey("threat_events.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("source_items.id", ondelete="CASCADE"), primary_key=True),
)


class ThreatEventRecord(Base):
    __tablename__ = "threat_events"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    geography: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    map_location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_uncertainties: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    contradictory_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    next_watch_items: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    implications: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    score: Mapped["ThreatScoreRecord"] = relationship(
        back_populates="threat",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    sources: Mapped[list["SourceItemRecord"]] = relationship(
        secondary=threat_sources,
        back_populates="threats",
        lazy="selectin",
    )
    extracted_claims: Mapped[list["ExtractedClaimRecord"]] = relationship(
        back_populates="threat",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    timeline: Mapped[list["ThreatTimelineEntryRecord"]] = relationship(
        back_populates="threat",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ThreatTimelineEntryRecord.occurred_at",
    )


class ThreatScoreRecord(Base):
    __tablename__ = "threat_scores"

    threat_id: Mapped[str] = mapped_column(
        ForeignKey("threat_events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    credibility: Mapped[float] = mapped_column(Float, nullable=False)
    velocity: Mapped[float] = mapped_column(Float, nullable=False)
    exposure: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    threat: Mapped[ThreatEventRecord] = relationship(back_populates="score")


class SourceItemRecord(Base):
    __tablename__ = "source_items"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reliability_tier: Mapped[str] = mapped_column(String(80), nullable=False)
    citation: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    threats: Mapped[list[ThreatEventRecord]] = relationship(
        secondary=threat_sources,
        back_populates="sources",
        lazy="selectin",
    )
    claims: Mapped[list["ExtractedClaimRecord"]] = relationship(
        back_populates="source",
        lazy="selectin",
    )


class ExtractedClaimRecord(Base):
    __tablename__ = "extracted_claims"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    threat_id: Mapped[str] = mapped_column(ForeignKey("threat_events.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    support_level: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_material: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contradicts_claim_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    threat: Mapped[ThreatEventRecord] = relationship(back_populates="extracted_claims")
    source: Mapped[SourceItemRecord] = relationship(back_populates="claims")


class ThreatTimelineEntryRecord(Base):
    __tablename__ = "threat_timeline_entries"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    threat_id: Mapped[str] = mapped_column(ForeignKey("threat_events.id", ondelete="CASCADE"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    material_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    threat: Mapped[ThreatEventRecord] = relationship(back_populates="timeline")


class IngestionRunRecord(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connector: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    data_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Recording order. Timestamps can tie on coarse clocks, so "latest run" is decided by this, not by time.
    sequence: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0", index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    item_count: Mapped[int] = mapped_column(nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
