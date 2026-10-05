"""Evidence-first normalization, snapshot persistence, and ingestion run tracking."""

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.http import FeedError
from app.core.time import utc_now
from app.db.models import IngestionRunRecord, ThreatEventRecord
from app.db.repository import get_threat_event, replace_threats, source_to_record
from app.domain.ingestion.base import Connector, RawSignal
from app.domain.ingestion.normalizer import normalize_raw_signal
from app.domain.threats.models import ThreatEvent, ThreatTimelineEntry
from app.domain.threats.scoring import ThreatScoreInput, calculate_threat_score
from app.domain.threats.status import ThreatStatus


@dataclass
class IngestionCounts:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


def threat_from_signal(raw: RawSignal) -> ThreatEvent:
    """Map only agency-reported facts; explain every unmeasured score input."""
    normalized = normalize_raw_signal(raw)
    magnitude = raw.details.get("magnitude")
    is_quake = raw.connector == "usgs_earthquakes"
    severity = max(0, min(100, float(magnitude) * 10)) if is_quake and magnitude is not None else 50
    score = calculate_threat_score(ThreatScoreInput(
        severity=severity, credibility=92, velocity=50, exposure=25, uncertainty_penalty=50,
    ))
    score.rationale.extend([
        "Policy v1: heuristic triage, not a calibrated risk estimate or probability of harm.",
        f"Severity proxy = clamp(reported magnitude × 10, 0, 100), using M {magnitude:g}; this is not an impact estimate."
        if is_quake and magnitude is not None else "Severity = 50: fixed unknown-severity baseline; no CVSS or impact severity was supplied.",
        "Credibility = 92: official-source policy for event existence; does not establish local exposure or impact.",
        "Velocity = 50: fixed unmeasured baseline; this feed does not establish a trend.",
        "Exposure = 25: conservative unmeasured baseline; no asset inventory or population exposure was supplied.",
        "Uncertainty = 50%: impact and exposure remain unmeasured. Score confidence is therefore low.",
    ])
    timestamp = raw.retrieved_at or utc_now()
    event_id = f"{'demo-' if raw.is_demo else ''}{raw.connector}-{raw.external_id}"
    summary = " ".join(raw.claims[:2])
    if raw.is_demo:
        summary = "DEMO fixture snapshot. " + summary
    uncertainties = [
        "This is a retrieved source snapshot; it does not imply continuous monitoring or current conditions.",
        "Impact, casualties, service disruptions, and local exposure have not been established by this feed."
        if is_quake else "Catalog inclusion does not establish that any particular organization's assets are affected or compromised.",
        "Scores use explicit policy baselines for unmeasured inputs and cannot be compared as calibrated risk across categories.",
    ]
    if is_quake and raw.details.get("review_status") == "automatic":
        uncertainties.append("USGS marks this event automatic; magnitude and location are preliminary and may be revised.")
    if is_quake and magnitude is None:
        uncertainties.append("Magnitude was not supplied by USGS.")
    if raw.is_demo:
        uncertainties.insert(0, "This is synthetic test data, not a live agency observation.")
    return ThreatEvent(
        id=event_id, title=raw.title, category=raw.category, geography=raw.geography,
        map_location=raw.map_location.model_copy(update={"source_id": normalized.source.id}) if raw.map_location else None,
        status=ThreatStatus.CONFIRMED,
        summary=summary, score=score, sources=[normalized.source], extracted_claims=normalized.claims,
        timeline=[ThreatTimelineEntry(
            id=f"{raw.id}-timeline", occurred_at=timestamp,
            title="Agency snapshot retrieved" if not raw.is_demo else "Demo fixture snapshot loaded",
            description=summary, source_ids=[raw.id],
        )],
        key_uncertainties=uncertainties,
        next_watch_items=["Review official event revisions and local emergency-management statements."]
        if is_quake else ["Check asset inventory against the vendor and product named by CISA.", "Review current official remediation guidance and applicable deadlines."],
        implications=["Assess local relevance using additional source-backed context before making operational decisions."],
        updated_at=raw.updated_at or timestamp, is_demo=raw.is_demo,
    )


def persist_signals(session: Session, signals: list[RawSignal]) -> IngestionCounts:
    """Upsert stable events; unchanged snapshots refresh retrieval time without duplicating history."""
    counts = IngestionCounts()
    for raw in signals:
        threat = threat_from_signal(raw)
        existing = get_threat_event(session, threat.id)
        if existing is not None:
            if raw.connector == "usgs_earthquakes" and raw.updated_at is not None and raw.updated_at < existing.updated_at:
                counts.unchanged += 1
                continue
            sources_by_id = {source.id: source for source in existing.sources}
            active_source_id = existing.extracted_claims[0].source_id if existing.extracted_claims else None
            active_source = sources_by_id.get(active_source_id)
            if active_source is not None and active_source.provenance.get("content_sha256") == raw.provenance.get("content_sha256"):
                source = threat.sources[0].model_copy(deep=True)
                source.id = active_source.id
                source.provenance["first_retrieved_at"] = active_source.provenance.get("first_retrieved_at")
                session.merge(source_to_record(source))
                # An upstream timestamp alone is metadata, not new material evidence.
                if raw.updated_at is not None:
                    session.get(ThreatEventRecord, threat.id).updated_at = raw.updated_at
                counts.unchanged += 1
                continue
            if raw.id in sources_by_id:
                # A → B → A is a new revision occurrence, not an unchanged current snapshot.
                raw = raw.model_copy(update={"id": f"{raw.id}-r{len(existing.timeline) + 1}"}, deep=True)
                threat = threat_from_signal(raw)
            # Keep earlier citations and timeline snapshots available; claims represent the current revision.
            threat.sources = existing.sources + threat.sources
            threat.timeline = existing.timeline + threat.timeline
            threat.timeline[-1].title = "Agency record revised" if not raw.is_demo else "Demo fixture revised"
            counts.updated += 1
        else:
            counts.inserted += 1
        replace_threats(session, [threat])
        session.flush()
    return counts


def record_run(session: Session, *, connector: str, data_mode: str, started_at: datetime,
               success: bool, item_count: int = 0, counts: IngestionCounts | None = None,
               error: str | None = None) -> IngestionRunRecord:
    counts = counts or IngestionCounts()
    sequence = (session.scalar(select(func.max(IngestionRunRecord.sequence))) or 0) + 1
    run = IngestionRunRecord(
        id=str(uuid4()), sequence=sequence, connector=connector, data_mode=data_mode, started_at=started_at,
        finished_at=utc_now(), success=success, item_count=item_count,
        inserted_count=counts.inserted, updated_count=counts.updated, unchanged_count=counts.unchanged,
        error=error,
    )
    session.add(run)
    return run


async def ingest_connector(session: Session, connector: Connector, *, fixture: dict | None = None) -> IngestionRunRecord:
    """Commit an entire validated feed or retain the existing snapshot and log failure."""
    started = utc_now()
    data_mode = "demo" if fixture is not None else "live"
    try:
        signals = connector.parse(fixture, retrieved_at=started, is_demo=True) if fixture is not None else await connector.fetch()
        counts = persist_signals(session, signals)
        run = record_run(session, connector=connector.name, data_mode=data_mode, started_at=started,
                         success=True, item_count=len(signals), counts=counts)
        session.commit()
        return run
    except Exception as error:
        session.rollback()
        # Validation errors are safe, concise messages. Do not persist SQL, headers, paths, or response bodies.
        message = str(error) if isinstance(error, FeedError) else f"Ingestion failed ({type(error).__name__})"
        run = record_run(session, connector=connector.name, data_mode=data_mode, started_at=started,
                         success=False, error=message[:500])
        session.commit()
        return run
