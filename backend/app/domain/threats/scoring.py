from pydantic import BaseModel, Field

from app.domain.threats.models import ConfidenceLabel, ThreatScore


class ThreatScoreInput(BaseModel):
    severity: float = Field(ge=0, le=100)
    credibility: float = Field(ge=0, le=100)
    velocity: float = Field(ge=0, le=100)
    exposure: float = Field(ge=0, le=100)
    uncertainty_penalty: float = Field(ge=0, le=100)
    contradiction_count: int = Field(default=0, ge=0)


def confidence_label_for(score_input: ThreatScoreInput) -> ConfidenceLabel:
    if (
        score_input.credibility >= 80
        and score_input.uncertainty_penalty <= 20
        and score_input.contradiction_count == 0
    ):
        return ConfidenceLabel.HIGH

    if (
        score_input.credibility >= 50
        and score_input.uncertainty_penalty <= 40
        and score_input.contradiction_count <= 1
    ):
        return ConfidenceLabel.MEDIUM

    return ConfidenceLabel.LOW


def calculate_threat_score(score_input: ThreatScoreInput) -> ThreatScore:
    """Calculate a transparent 0 to 100 priority score.

    Formula:
    priority = severity% * credibility% * velocity% * exposure% * 100
    priority is then multiplied by (1 - uncertainty_penalty%).
    """
    raw_priority = (
        (score_input.severity / 100)
        * (score_input.credibility / 100)
        * (score_input.velocity / 100)
        * (score_input.exposure / 100)
        * 100
    )
    uncertainty_multiplier = 1 - (score_input.uncertainty_penalty / 100)
    priority = round(raw_priority * uncertainty_multiplier, 2)

    rationale = [
        "Priority = severity% × credibility% × velocity% × exposure% × 100 × (1 − uncertainty%).",
        f"Severity input: {score_input.severity:.1f}/100.",
        f"Credibility input: {score_input.credibility:.1f}/100.",
        f"Velocity input: {score_input.velocity:.1f}/100.",
        f"Exposure input: {score_input.exposure:.1f}/100.",
        f"Uncertainty penalty: {score_input.uncertainty_penalty:.1f}%.",
    ]
    if score_input.contradiction_count:
        rationale.append(f"Contradictory evidence count: {score_input.contradiction_count}.")

    return ThreatScore(
        severity=score_input.severity,
        credibility=score_input.credibility,
        velocity=score_input.velocity,
        exposure=score_input.exposure,
        uncertainty_penalty=score_input.uncertainty_penalty,
        priority=priority,
        confidence=confidence_label_for(score_input),
        rationale=rationale,
    )
