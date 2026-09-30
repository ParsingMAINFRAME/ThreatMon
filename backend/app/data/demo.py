from datetime import UTC, datetime

from app.domain.sources.models import (
    ClaimSupportLevel,
    ExtractedClaim,
    SourceItem,
    SourceReliabilityTier,
    SourceType,
)
from app.domain.threats.models import MapLocation, ThreatCategory, ThreatEvent, ThreatTimelineEntry
from app.domain.threats.scoring import ThreatScoreInput, calculate_threat_score
from app.domain.threats.status import ThreatStatus


DEMO_TIMESTAMP = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


def _source(
    *,
    id: str,
    title: str,
    source_name: str,
    source_type: SourceType,
    reliability_tier: SourceReliabilityTier,
    citation: str,
    is_official: bool,
    notes: str | None = None,
) -> SourceItem:
    return SourceItem(
        id=id,
        title=title,
        source_name=source_name,
        source_type=source_type,
        reliability_tier=reliability_tier,
        citation=citation,
        published_at=DEMO_TIMESTAMP,
        retrieved_at=DEMO_TIMESTAMP,
        is_official=is_official,
        is_demo=True,
        notes=notes,
    )


def _claim(
    *,
    id: str,
    source_id: str,
    text: str,
    support_level: ClaimSupportLevel,
    confidence: float,
    contradicts_claim_ids: list[str] | None = None,
) -> ExtractedClaim:
    return ExtractedClaim(
        id=id,
        source_id=source_id,
        text=text,
        support_level=support_level,
        confidence=confidence,
        contradicts_claim_ids=contradicts_claim_ids or [],
    )


def seeded_threats() -> list[ThreatEvent]:
    asteroid_source = _source(
        id="demo-source-neo-001",
        title="DEMO record: routine near-Earth object close approach",
        source_name="DEMO NASA CNEOS-style feed",
        source_type=SourceType.OFFICIAL,
        reliability_tier=SourceReliabilityTier.VERY_HIGH,
        citation="DEMO-CNEOS-001 local seeded record; not live NASA data",
        is_official=True,
        notes="Local demo citation. No orbital values are represented as live facts.",
    )
    earthquake_source = _source(
        id="demo-source-quake-001",
        title="DEMO record: official earthquake alert",
        source_name="DEMO USGS-style alert feed",
        source_type=SourceType.OFFICIAL,
        reliability_tier=SourceReliabilityTier.VERY_HIGH,
        citation="DEMO-USGS-001 local seeded record; not live USGS data",
        is_official=True,
    )
    cyber_source = _source(
        id="demo-source-cyber-001",
        title="DEMO record: exploited vulnerability added to official catalog",
        source_name="DEMO CISA KEV-style catalog",
        source_type=SourceType.OFFICIAL,
        reliability_tier=SourceReliabilityTier.VERY_HIGH,
        citation="DEMO-CISA-KEV-001 local seeded record; not live CISA data",
        is_official=True,
        notes="No exploit instructions, indicators, or weaponization details are included.",
    )
    public_health_source = _source(
        id="demo-source-health-001",
        title="DEMO record: unconfirmed local public-health signal",
        source_name="DEMO local report aggregator",
        source_type=SourceType.LOCAL_REPORT,
        reliability_tier=SourceReliabilityTier.LOW,
        citation="DEMO-LOCAL-HEALTH-001 local seeded record; unconfirmed demo signal",
        is_official=False,
    )
    public_health_check_source = _source(
        id="demo-source-health-002",
        title="DEMO record: no matching official confirmation in local demo set",
        source_name="DEMO public-health agency watch log",
        source_type=SourceType.OFFICIAL,
        reliability_tier=SourceReliabilityTier.HIGH,
        citation="DEMO-AGENCY-WATCH-001 local seeded record; absence note is demo-only",
        is_official=True,
    )

    return [
        ThreatEvent(
            id="demo-neo-routine-flyby",
            title="[DEMO] Routine near-Earth object close approach",
            category=ThreatCategory.SPACE_PLANETARY,
            geography=["Global", "Near-Earth space"],
            status=ThreatStatus.ROUTINE,
            summary=(
                "A local demo record represents a routine asteroid close approach. "
                "The record is low priority and is not live planetary-risk intelligence."
            ),
            score=calculate_threat_score(
                ThreatScoreInput(
                    severity=8,
                    credibility=88,
                    velocity=10,
                    exposure=5,
                    uncertainty_penalty=5,
                )
            ),
            sources=[asteroid_source],
            extracted_claims=[
                _claim(
                    id="demo-claim-neo-001",
                    source_id=asteroid_source.id,
                    text="The demo event is categorized as a routine close approach, not an impact warning.",
                    support_level=ClaimSupportLevel.CONFIRMED,
                    confidence=0.9,
                )
            ],
            timeline=[
                ThreatTimelineEntry(
                    id="demo-timeline-neo-001",
                    occurred_at=DEMO_TIMESTAMP,
                    title="Demo routine flyby record created",
                    description="Seeded CNEOS-style demo source marks the event as routine.",
                    source_ids=[asteroid_source.id],
                )
            ],
            key_uncertainties=[
                "This is a seeded local demo record and does not contain live orbital data.",
            ],
            contradictory_evidence=[],
            next_watch_items=[
                "Replace the seeded record with a read-only NASA CNEOS connector in a later milestone.",
            ],
            implications=[
                "No operational, supply-chain, or market implication is represented by this demo record.",
            ],
            updated_at=DEMO_TIMESTAMP,
            is_demo=True,
        ),
        ThreatEvent(
            id="demo-official-earthquake-alert",
            title="[DEMO] Official earthquake alert with infrastructure watch",
            category=ThreatCategory.NATURAL_HAZARD,
            geography=["Pacific region", "Demo coastal metro"],
            map_location=MapLocation(
                lon=142.5, lat=35.5, label="Synthetic western Pacific epicenter — illustrative demo point",
                origin="synthetic_demo", precision="illustrative", source_id=earthquake_source.id,
            ),
            status=ThreatStatus.CONFIRMED,
            summary=(
                "A local demo official-source earthquake alert is treated as high credibility. "
                "Potential impacts are framed around response posture and infrastructure monitoring."
            ),
            score=calculate_threat_score(
                ThreatScoreInput(
                    severity=76,
                    credibility=93,
                    velocity=66,
                    exposure=70,
                    uncertainty_penalty=10,
                )
            ),
            sources=[earthquake_source],
            extracted_claims=[
                _claim(
                    id="demo-claim-quake-001",
                    source_id=earthquake_source.id,
                    text="The demo alert is official-source and therefore high credibility for event existence.",
                    support_level=ClaimSupportLevel.CONFIRMED,
                    confidence=0.92,
                )
            ],
            timeline=[
                ThreatTimelineEntry(
                    id="demo-timeline-quake-001",
                    occurred_at=DEMO_TIMESTAMP,
                    title="Official demo alert published",
                    description="Seeded USGS-style source creates a confirmed natural-hazard demo event.",
                    source_ids=[earthquake_source.id],
                )
            ],
            key_uncertainties=[
                "Damage, casualties, and infrastructure effects are not asserted in the seeded demo data.",
                "Aftershock and service-disruption details would require live official updates.",
            ],
            contradictory_evidence=[],
            next_watch_items=[
                "Official aftershock updates.",
                "Local emergency-management notices.",
                "Transport, power, port, and telecom service statements.",
            ],
            implications=[
                "Potential short-term logistics and infrastructure monitoring need in the affected demo geography.",
                "No investment conclusion is made from the seeded alert.",
            ],
            updated_at=DEMO_TIMESTAMP,
            is_demo=True,
        ),
        ThreatEvent(
            id="demo-exploited-cyber-vulnerability",
            title="[DEMO] Exploited vulnerability in widely deployed edge appliance",
            category=ThreatCategory.CYBERSECURITY,
            geography=["Global"],
            status=ThreatStatus.CONFIRMED,
            summary=(
                "A local demo CISA KEV-style record represents confirmed exploitation of a widely deployed "
                "edge appliance vulnerability. The demo intentionally omits exploit and weaponization details."
            ),
            score=calculate_threat_score(
                ThreatScoreInput(
                    severity=82,
                    credibility=96,
                    velocity=72,
                    exposure=68,
                    uncertainty_penalty=8,
                )
            ),
            sources=[cyber_source],
            extracted_claims=[
                _claim(
                    id="demo-claim-cyber-001",
                    source_id=cyber_source.id,
                    text="The seeded demo catalog record marks the vulnerability as exploited in the wild.",
                    support_level=ClaimSupportLevel.CONFIRMED,
                    confidence=0.94,
                )
            ],
            timeline=[
                ThreatTimelineEntry(
                    id="demo-timeline-cyber-001",
                    occurred_at=DEMO_TIMESTAMP,
                    title="Demo KEV-style entry added",
                    description="Seeded official catalog-style source establishes high-credibility exploitation status.",
                    source_ids=[cyber_source.id],
                )
            ],
            key_uncertainties=[
                "Affected customer counts and sector exposure are not asserted in the seeded demo data.",
                "Vendor remediation status is represented only as a future watch item.",
            ],
            contradictory_evidence=[],
            next_watch_items=[
                "Vendor advisory updates.",
                "Official remediation deadline updates.",
                "Sector-specific exposure reporting from reputable sources.",
            ],
            implications=[
                "Potential operational exposure for organizations with internet-facing edge appliances.",
                "Potential public-company relevance only if future source-backed vendor or sector exposure is added.",
            ],
            updated_at=DEMO_TIMESTAMP,
            is_demo=True,
        ),
        ThreatEvent(
            id="demo-unconfirmed-public-health-signal",
            title="[DEMO] Unconfirmed public-health signal under watch",
            category=ThreatCategory.PUBLIC_HEALTH,
            geography=["Demo province"],
            map_location=MapLocation(
                lon=105.5, lat=15.5, label="Synthetic Southeast Asia health signal — illustrative demo point",
                origin="synthetic_demo", precision="illustrative", source_id=public_health_source.id,
            ),
            status=ThreatStatus.WATCHLIST,
            summary=(
                "A local demo report suggests a public-health signal, but the event remains unconfirmed. "
                "The record preserves uncertainty and incomplete source coverage instead of presenting confirmation."
            ),
            score=calculate_threat_score(
                ThreatScoreInput(
                    severity=55,
                    credibility=38,
                    velocity=45,
                    exposure=30,
                    uncertainty_penalty=35,
                    contradiction_count=0,
                )
            ),
            sources=[public_health_source, public_health_check_source],
            extracted_claims=[
                _claim(
                    id="demo-claim-health-001",
                    source_id=public_health_source.id,
                    text="A local demo report describes an unusual public-health signal.",
                    support_level=ClaimSupportLevel.SINGLE_SOURCE,
                    confidence=0.42,
                ),
                _claim(
                    id="demo-claim-health-002",
                    source_id=public_health_check_source.id,
                    text="The seeded demo agency watch log does not contain an official confirmation.",
                    support_level=ClaimSupportLevel.UNKNOWN,
                    confidence=0.5,
                ),
            ],
            timeline=[
                ThreatTimelineEntry(
                    id="demo-timeline-health-001",
                    occurred_at=DEMO_TIMESTAMP,
                    title="Unconfirmed demo signal logged",
                    description="Single local demo source creates a watchlist item with low to medium credibility.",
                    source_ids=[public_health_source.id],
                ),
                ThreatTimelineEntry(
                    id="demo-timeline-health-002",
                    occurred_at=DEMO_TIMESTAMP,
                    title="Official confirmation absent from demo watch log",
                    description="An incomplete demo watch log lacks confirmation; this does not disprove the local report.",
                    source_ids=[public_health_check_source.id],
                ),
            ],
            key_uncertainties=[
                "No live official health-agency confirmation is included.",
                "Case counts, pathogen details, transmission claims, and clinical specifics are not asserted.",
                "The source support is weak and may represent noise or misclassification.",
            ],
            contradictory_evidence=[],
            next_watch_items=[
                "Official health-agency bulletin.",
                "Reputable public-health reporting with named sourcing.",
                "Clear geography and case-definition clarification.",
            ],
            implications=[
                "Operational implication is limited to monitoring until source support improves.",
                "No market or company impact is asserted from this unconfirmed demo signal.",
            ],
            updated_at=DEMO_TIMESTAMP,
            is_demo=True,
        ),
    ]


def threat_by_id(threat_id: str) -> ThreatEvent | None:
    return next((threat for threat in seeded_threats() if threat.id == threat_id), None)
