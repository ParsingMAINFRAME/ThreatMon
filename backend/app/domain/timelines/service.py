from app.domain.threats.models import ThreatEvent, ThreatTimelineEntry


def material_timeline(event: ThreatEvent) -> list[ThreatTimelineEntry]:
    return [entry for entry in event.timeline if entry.material_change]
