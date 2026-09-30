from app.domain.sources.models import SourceItem, SourceReliabilityTier, SourceType
from app.domain.sources.reliability import aggregate_source_reliability, source_reliability_weight


def test_official_source_gets_high_weight() -> None:
    source = SourceItem(
        id="source-1",
        title="Official bulletin",
        source_name="Official agency",
        source_type=SourceType.OFFICIAL,
        reliability_tier=SourceReliabilityTier.VERY_HIGH,
        citation="TEST-OFFICIAL",
        is_official=True,
    )

    assert source_reliability_weight(source) == 0.97


def test_social_or_community_source_gets_low_weight() -> None:
    source = SourceItem(
        id="source-2",
        title="Community post",
        source_name="Community forum",
        source_type=SourceType.SOCIAL_OR_COMMUNITY,
        reliability_tier=SourceReliabilityTier.LOW,
        citation="TEST-COMMUNITY",
        is_official=False,
    )

    assert source_reliability_weight(source) == 0.15


def test_aggregate_reliability_adds_small_corroboration_bonus() -> None:
    sources = [
        SourceItem(
            id="source-1",
            title="Official bulletin",
            source_name="Official agency",
            source_type=SourceType.OFFICIAL,
            reliability_tier=SourceReliabilityTier.VERY_HIGH,
            citation="TEST-OFFICIAL",
            is_official=True,
        ),
        SourceItem(
            id="source-2",
            title="Reputable report",
            source_name="Reputable news",
            source_type=SourceType.REPUTABLE_NEWS,
            reliability_tier=SourceReliabilityTier.MEDIUM,
            citation="TEST-NEWS",
            is_official=False,
        ),
    ]

    assert aggregate_source_reliability(sources) == 0.86
