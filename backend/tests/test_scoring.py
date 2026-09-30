from app.domain.threats.models import ConfidenceLabel
from app.domain.threats.scoring import ThreatScoreInput, calculate_threat_score


def test_priority_score_uses_multiplicative_formula() -> None:
    score = calculate_threat_score(
        ThreatScoreInput(
            severity=100,
            credibility=100,
            velocity=100,
            exposure=100,
            uncertainty_penalty=0,
        )
    )

    assert score.priority == 100
    assert score.confidence == ConfidenceLabel.HIGH


def test_uncertainty_penalty_reduces_priority() -> None:
    no_penalty = calculate_threat_score(
        ThreatScoreInput(
            severity=80,
            credibility=80,
            velocity=80,
            exposure=80,
            uncertainty_penalty=0,
        )
    )
    penalized = calculate_threat_score(
        ThreatScoreInput(
            severity=80,
            credibility=80,
            velocity=80,
            exposure=80,
            uncertainty_penalty=50,
        )
    )

    assert penalized.priority == round(no_penalty.priority * 0.5, 2)


def test_low_credibility_and_contradiction_produce_low_confidence() -> None:
    score = calculate_threat_score(
        ThreatScoreInput(
            severity=70,
            credibility=38,
            velocity=50,
            exposure=40,
            uncertainty_penalty=35,
            contradiction_count=1,
        )
    )

    assert score.confidence == ConfidenceLabel.LOW
    assert any("Contradictory evidence count" in item for item in score.rationale)
