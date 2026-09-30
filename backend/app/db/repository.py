from datetime import UTC, datetime
import hashlib
import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    ExtractedClaimRecord,
    SourceItemRecord,
    ThreatEventRecord,
    ThreatScoreRecord,
    ThreatTimelineEntryRecord,
    threat_sources,
)
from app.domain.sources.models import (
    ExtractedClaim,
    SourceItem,
    SourceReliabilityTier,
    SourceType,
)
from app.domain.threats.models import ConfidenceLabel, ThreatCategory, ThreatEvent, ThreatScore, ThreatTimelineEntry
from app.domain.threats.schemas import ThreatCard
from app.domain.threats.status import ThreatStatus


def _utc(value: datetime | None) -> datetime | None:
    # SQLite drops tzinfo; all stored application timestamps are UTC.
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def source_to_record(source: SourceItem) -> SourceItemRecord:
    return SourceItemRecord(
        id=source.id,
        title=source.title,
        source_name=source.source_name,
        source_type=source.source_type.value,
        reliability_tier=source.reliability_tier.value,
        citation=source.citation,
        url=source.url,
        published_at=source.published_at,
        retrieved_at=source.retrieved_at,
        is_official=source.is_official,
        is_demo=source.is_demo,
        notes=source.notes,
        provenance=source.provenance,
    )


def score_to_record(threat_id: str, score: ThreatScore) -> ThreatScoreRecord:
    return ThreatScoreRecord(
        threat_id=threat_id,
        severity=score.severity,
        credibility=score.credibility,
        velocity=score.velocity,
        exposure=score.exposure,
        uncertainty_penalty=score.uncertainty_penalty,
        priority=score.priority,
        confidence=score.confidence.value,
        rationale=score.rationale,
    )


def claim_to_record(threat_id: str, claim: ExtractedClaim) -> ExtractedClaimRecord:
    return ExtractedClaimRecord(
        id=claim.id,
        threat_id=threat_id,
        source_id=claim.source_id,
        text=claim.text,
        support_level=claim.support_level.value,
        confidence=claim.confidence,
        is_material=claim.is_material,
        contradicts_claim_ids=claim.contradicts_claim_ids,
    )


def timeline_to_record(threat_id: str, entry: ThreatTimelineEntry) -> ThreatTimelineEntryRecord:
    return ThreatTimelineEntryRecord(
        id=entry.id,
        threat_id=threat_id,
        occurred_at=entry.occurred_at,
        title=entry.title,
        description=entry.description,
        source_ids=entry.source_ids,
        material_change=entry.material_change,
    )


def threat_to_record(threat: ThreatEvent, sources_by_id: dict[str, SourceItemRecord]) -> ThreatEventRecord:
    record = ThreatEventRecord(
        id=threat.id,
        title=threat.title,
        category=threat.category.value,
        geography=threat.geography,
        map_location=threat.map_location.model_dump(mode="json") if threat.map_location else None,
        status=threat.status.value,
        summary=threat.summary,
        key_uncertainties=threat.key_uncertainties,
        contradictory_evidence=threat.contradictory_evidence,
        next_watch_items=threat.next_watch_items,
        implications=threat.implications,
        updated_at=threat.updated_at,
        is_demo=threat.is_demo,
    )
    record.score = score_to_record(threat.id, threat.score)
    record.sources = [sources_by_id[source.id] for source in threat.sources]
    record.extracted_claims = [claim_to_record(threat.id, claim) for claim in threat.extracted_claims]
    record.timeline = [timeline_to_record(threat.id, entry) for entry in threat.timeline]
    return record


def source_from_record(record: SourceItemRecord) -> SourceItem:
    return SourceItem(
        id=record.id,
        title=record.title,
        source_name=record.source_name,
        source_type=SourceType(record.source_type),
        reliability_tier=SourceReliabilityTier(record.reliability_tier),
        citation=record.citation,
        url=record.url,
        published_at=_utc(record.published_at),
        retrieved_at=_utc(record.retrieved_at),
        is_official=record.is_official,
        is_demo=record.is_demo,
        notes=record.notes,
        provenance=record.provenance,
    )


def score_from_record(record: ThreatScoreRecord) -> ThreatScore:
    return ThreatScore(
        severity=record.severity,
        credibility=record.credibility,
        velocity=record.velocity,
        exposure=record.exposure,
        uncertainty_penalty=record.uncertainty_penalty,
        priority=record.priority,
        confidence=ConfidenceLabel(record.confidence),
        rationale=record.rationale,
    )


def claim_from_record(record: ExtractedClaimRecord) -> ExtractedClaim:
    return ExtractedClaim(
        id=record.id,
        source_id=record.source_id,
        text=record.text,
        support_level=record.support_level,
        confidence=record.confidence,
        is_material=record.is_material,
        contradicts_claim_ids=record.contradicts_claim_ids,
    )


def timeline_from_record(record: ThreatTimelineEntryRecord) -> ThreatTimelineEntry:
    return ThreatTimelineEntry(
        id=record.id,
        occurred_at=_utc(record.occurred_at),
        title=record.title,
        description=record.description,
        source_ids=record.source_ids,
        material_change=record.material_change,
    )


def threat_from_record(record: ThreatEventRecord) -> ThreatEvent:
    return ThreatEvent(
        id=record.id,
        title=record.title,
        category=ThreatCategory(record.category),
        geography=record.geography,
        map_location=record.map_location,
        status=ThreatStatus(record.status),
        summary=record.summary,
        score=score_from_record(record.score),
        sources=[source_from_record(source) for source in record.sources],
        extracted_claims=[claim_from_record(claim) for claim in record.extracted_claims],
        timeline=[timeline_from_record(entry) for entry in record.timeline],
        key_uncertainties=record.key_uncertainties,
        contradictory_evidence=record.contradictory_evidence,
        next_watch_items=record.next_watch_items,
        implications=record.implications,
        updated_at=_utc(record.updated_at),
        is_demo=record.is_demo,
    )


def _threat_options():
    return (
        selectinload(ThreatEventRecord.score),
        selectinload(ThreatEventRecord.sources),
        selectinload(ThreatEventRecord.extracted_claims),
        selectinload(ThreatEventRecord.timeline),
    )


def list_threat_events(session: Session) -> list[ThreatEvent]:
    records = session.scalars(
        select(ThreatEventRecord)
        .options(*_threat_options())
        .join(ThreatScoreRecord)
        .order_by(ThreatScoreRecord.priority.desc(), ThreatEventRecord.updated_at.desc(), ThreatEventRecord.id)
    ).all()
    return [threat_from_record(record) for record in records]


def get_threat_event(session: Session, threat_id: str) -> ThreatEvent | None:
    record = session.scalar(
        select(ThreatEventRecord)
        .options(*_threat_options())
        .where(ThreatEventRecord.id == threat_id)
    )
    return threat_from_record(record) if record else None


def list_source_items(session: Session) -> list[SourceItem]:
    records = session.scalars(select(SourceItemRecord).order_by(SourceItemRecord.source_name, SourceItemRecord.id)).all()
    return [source_from_record(record) for record in records]


def replace_threats(session: Session, threats: list[ThreatEvent]) -> None:
    source_records: dict[str, SourceItemRecord] = {}
    for threat in threats:
        for source in threat.sources:
            if source.id not in source_records:
                source_records[source.id] = source_to_record(source)

    for source in source_records.values():
        session.merge(source)
    session.flush()

    persisted_sources = {
        source.id: session.get(SourceItemRecord, source.id)
        for source in source_records.values()
    }

    for threat in threats:
        existing = session.get(ThreatEventRecord, threat.id)
        if existing is not None:
            session.delete(existing)
            session.flush()
        session.add(threat_to_record(threat, persisted_sources))


def query_threat_cards(session: Session, *, q: str | None = None, category: ThreatCategory | None = None,
                        status: ThreatStatus | None = None, data_mode: str | None = None,
                        min_priority: float = 0, sort: str = "priority", limit: int = 50,
                        offset: int = 0) -> tuple[list[ThreatCard], int, str, str]:
    """Read one complete card snapshot, then fingerprint and slice it for pagination.

    A single SQL statement keeps cards, source counts, total, and data mode consistent
    within a response even during ingestion. The digest lets clients detect a change
    between page requests without storing historical collections on the server.
    """
    predicates = [ThreatScoreRecord.priority >= min_priority]
    if q and q.strip():
        search = q.strip().lower()
        predicates.append(or_(func.lower(ThreatEventRecord.title).contains(search, autoescape=True),
                              func.lower(ThreatEventRecord.summary).contains(search, autoescape=True)))
    if category is not None:
        predicates.append(ThreatEventRecord.category == category.value)
    if status is not None:
        predicates.append(ThreatEventRecord.status == status.value)
    if data_mode is not None:
        predicates.append(ThreatEventRecord.is_demo == (data_mode == "demo"))
    ordering = (ThreatScoreRecord.priority.desc(), ThreatEventRecord.updated_at.desc(), ThreatEventRecord.id)
    if sort == "updated":
        ordering = (ThreatEventRecord.updated_at.desc(), ThreatScoreRecord.priority.desc(), ThreatEventRecord.id)
    source_count = (select(func.count()).select_from(threat_sources)
                    .where(threat_sources.c.threat_id == ThreatEventRecord.id)
                    .correlate(ThreatEventRecord).scalar_subquery().label("source_count"))
    card_columns = [getattr(ThreatEventRecord, name) for name in (
        "id", "title", "category", "geography", "map_location", "status", "summary", "updated_at", "is_demo",
    )]
    score_columns = [getattr(ThreatScoreRecord, name) for name in ThreatScore.model_fields]
    rows = session.execute(
        select(*card_columns, *score_columns, source_count)
        .join(ThreatScoreRecord, ThreatEventRecord.id == ThreatScoreRecord.threat_id)
        .where(*predicates).order_by(*ordering)
    ).mappings().all()
    cards = []
    for row in rows:
        data = dict(row)
        score = {name: data.pop(name) for name in ThreatScore.model_fields}
        data["updated_at"] = _utc(data["updated_at"]).isoformat()
        cards.append(ThreatCard.model_validate({**data, "score": score}))
    total = len(cards)
    demo_total = sum(card.is_demo for card in cards)
    mode = "empty" if total == 0 else "demo" if demo_total == total else "live" if demo_total == 0 else "mixed"
    content = json.dumps([card.model_dump(mode="json") for card in cards],
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    snapshot_id = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return cards[offset:offset + limit], total, mode, snapshot_id
