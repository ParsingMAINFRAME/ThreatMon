from pydantic import BaseModel

from app.domain.ingestion.base import RawSignal
from app.domain.sources.models import (
    ClaimSupportLevel,
    ExtractedClaim,
    SourceItem,
    SourceReliabilityTier,
    SourceType,
)


class NormalizedSignal(BaseModel):
    source: SourceItem
    claims: list[ExtractedClaim]


def reliability_tier_for_source(source_type: SourceType, is_official: bool) -> SourceReliabilityTier:
    if is_official or source_type == SourceType.OFFICIAL:
        return SourceReliabilityTier.VERY_HIGH
    if source_type in {SourceType.VENDOR, SourceType.PUBLIC_DATASET}:
        return SourceReliabilityTier.HIGH
    if source_type == SourceType.REPUTABLE_NEWS:
        return SourceReliabilityTier.MEDIUM
    if source_type in {SourceType.LOCAL_REPORT, SourceType.SOCIAL_OR_COMMUNITY}:
        return SourceReliabilityTier.LOW
    return SourceReliabilityTier.UNKNOWN


def support_level_for_source(source_type: SourceType, is_official: bool) -> ClaimSupportLevel:
    if is_official or source_type == SourceType.OFFICIAL:
        return ClaimSupportLevel.CONFIRMED
    return ClaimSupportLevel.SINGLE_SOURCE


def normalize_raw_signal(raw: RawSignal) -> NormalizedSignal:
    source = SourceItem(
        id=raw.id,
        title=raw.title,
        source_name=raw.source_name,
        source_type=raw.source_type,
        reliability_tier=reliability_tier_for_source(raw.source_type, raw.is_official),
        citation=raw.citation,
        url=raw.url,
        published_at=raw.published_at,
        retrieved_at=raw.retrieved_at,
        is_official=raw.is_official,
        is_demo=raw.is_demo,
        provenance=raw.provenance,
        notes=("An official record supports event existence, not local impact or exposure. "
               "Revisions from the same agency are not independent corroboration.") if raw.is_official else None,
    )

    support_level = support_level_for_source(raw.source_type, raw.is_official)
    claim_confidence = 0.85 if support_level == ClaimSupportLevel.CONFIRMED else 0.45
    claims = [
        ExtractedClaim(
            id=f"{raw.id}-claim-{index + 1}",
            source_id=raw.id,
            text=claim,
            support_level=support_level,
            confidence=claim_confidence,
        )
        for index, claim in enumerate(raw.claims)
    ]

    return NormalizedSignal(source=source, claims=claims)
