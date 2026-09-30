from app.domain.ingestion.base import RawSignal
from app.domain.ingestion.normalizer import normalize_raw_signal
from app.domain.sources.models import ClaimSupportLevel, SourceReliabilityTier, SourceType
from app.domain.threats.models import ThreatCategory


def test_official_raw_signal_becomes_confirmed_claim() -> None:
    raw = RawSignal(
        id="raw-1",
        title="Official alert",
        source_name="Official agency",
        source_type=SourceType.OFFICIAL,
        category=ThreatCategory.NATURAL_HAZARD,
        citation="TEST-OFFICIAL",
        claims=["Official event exists."],
        is_official=True,
    )

    normalized = normalize_raw_signal(raw)

    assert normalized.source.reliability_tier == SourceReliabilityTier.VERY_HIGH
    assert normalized.claims[0].support_level == ClaimSupportLevel.CONFIRMED
    assert normalized.claims[0].confidence == 0.85


def test_local_raw_signal_remains_single_source() -> None:
    raw = RawSignal(
        id="raw-2",
        title="Local report",
        source_name="Local report aggregator",
        source_type=SourceType.LOCAL_REPORT,
        category=ThreatCategory.PUBLIC_HEALTH,
        citation="TEST-LOCAL",
        claims=["A local signal was reported."],
        is_official=False,
    )

    normalized = normalize_raw_signal(raw)

    assert normalized.source.reliability_tier == SourceReliabilityTier.LOW
    assert normalized.claims[0].support_level == ClaimSupportLevel.SINGLE_SOURCE
    assert normalized.claims[0].confidence == 0.45
