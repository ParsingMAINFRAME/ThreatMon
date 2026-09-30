from app.domain.threats.models import ThreatEvent


def visible_implications(event: ThreatEvent) -> list[str]:
    """Return already sourced implication notes from the threat record."""
    return event.implications
