from app.domain.sources.models import SourceItem, SourceReliabilityTier, SourceType


BASE_SOURCE_WEIGHTS: dict[SourceType, float] = {
    SourceType.OFFICIAL: 0.92,
    SourceType.VENDOR: 0.82,
    SourceType.PUBLIC_DATASET: 0.8,
    SourceType.REPUTABLE_NEWS: 0.72,
    SourceType.LOCAL_REPORT: 0.48,
    SourceType.SOCIAL_OR_COMMUNITY: 0.3,
    SourceType.UNKNOWN: 0.2,
}


TIER_ADJUSTMENTS: dict[SourceReliabilityTier, float] = {
    SourceReliabilityTier.VERY_HIGH: 0.08,
    SourceReliabilityTier.HIGH: 0.04,
    SourceReliabilityTier.MEDIUM: 0.0,
    SourceReliabilityTier.LOW: -0.12,
    SourceReliabilityTier.UNKNOWN: -0.04,
}


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def source_reliability_weight(source: SourceItem) -> float:
    """Return a deterministic source reliability weight on a 0.0 to 1.0 scale."""
    base = BASE_SOURCE_WEIGHTS[source.source_type]
    if source.is_official:
        base = max(base, BASE_SOURCE_WEIGHTS[SourceType.OFFICIAL])
    adjusted = base + TIER_ADJUSTMENTS[source.reliability_tier]
    if source.url is None:
        adjusted -= 0.03
    return round(clamp_unit(adjusted), 3)


def aggregate_source_reliability(sources: list[SourceItem]) -> float:
    if not sources:
        return 0.0

    weights = [source_reliability_weight(source) for source in sources]
    corroboration_bonus = min(0.12, 0.03 * max(0, len(sources) - 1))
    return round(clamp_unit((sum(weights) / len(weights)) + corroboration_bonus), 3)
