"""Synthetic editorial fixtures. No publisher, incident, or live observation is represented."""

from datetime import UTC, datetime, timedelta

from app.news.models import NewsArticle, NewsEvent, NewsLocation, NewsResponse
from app.news.urls import ArticleCandidate, deduplicate_articles

DEMO_AS_OF = datetime(2026, 9, 30, 12, tzinfo=UTC)
PUBLISHERS = ["DEMO Lantern Gazette", "DEMO Meridian Ledger", "DEMO Copperline Dispatch", "DEMO Atlas Notebook",
              "DEMO Paper Coast Review", "DEMO Fieldglass Journal", "DEMO Quiet Horizon Bulletin"]
IRAN_ANGLES = [
    "Initial report awaits verification", "Agency confirmation absent from scenario", "Location details remain uncertain",
    "Independent review of the first dispatch", "Transport checks requested in the exercise", "No verified impact count in the scenario",
    "A second account adds no confirmation", "Exercise desk requests source documents", "Community account remains uncorroborated",
    "Timeline of synthetic dispatches assembled", "Analysts distinguish repetition from evidence", "Simulated utility status remains unknown",
    "Local-response details await a cited update", "Unverified imagery excluded from assessment", "Scenario watch maintains uncertainty",
    "Separate unrelated event kept outside this record", "Exercise brief records conflicting location descriptions", "Reported sound is not evidence of cause",
    "Rumor volume does not change verification state", "Transport bulletin requested for corroboration", "Synthetic evening desk reviews provenance",
    "No attribution established in the exercise", "Editorial review preserves unanswered questions", "Reported disruption has no verified extent",
    "Scenario sources distinguish publication from confirmation", "Public guidance is not invented for this exercise", "Analysts request an official statement",
    "Simulated supply-route relevance remains unassessed", "Exercise bulletin corrects an earlier timestamp", "Local reporting breadth grows without confirmation",
    "Duplicated dispatch identified by the exercise desk", "Scenario response posture remains unspecified", "Assessment keeps high severity as an assumption",
    "Final exercise update still lacks corroboration", "Handoff lists the evidence needed next",
]


def _point(lat: float, lon: float, label: str) -> NewsLocation:
    return NewsLocation(lat=lat, lon=lon, label=f"DEMO {label}", precision="illustrative", confidence="unknown",
                        basis="Synthetic scenario position for interface testing; not a reported incident coordinate or impact area.")


def _stories(event_id: str, subject: str, count: int, hours: list[float], angles: list[str] | None = None) -> list[ArticleCandidate]:
    items = []
    for index in range(count):
        article_id = f"{event_id}-story-{index + 1:02d}"
        angle = angles[index] if angles else f"Synthetic desk update {index + 1:02d}"
        item = NewsArticle(id=article_id, canonical_url=None, headline=f"DEMO {subject}: {angle}",
                           publisher=PUBLISHERS[index % len(PUBLISHERS)], published_at=DEMO_AS_OF - timedelta(hours=hours[index]),
                           retrieved_at=DEMO_AS_OF, summary=f"DEMO synthetic dispatch for {subject}. {angle}. This fixture makes no claim about a real incident.",
                           is_demo=True, syndication_key=f"demo-wire-{article_id}", duplicate_urls=[])
        items.append(ArticleCandidate(item, f"https://fixtures.example.invalid/{article_id}"))
    return items


def demo_news() -> NewsResponse:
    scenarios = [
        ("demo-iran-explosion", "Iran reported explosion exercise", "unconfirmed", "high", "geopolitical_infrastructure", _point(35.69, 51.42, "illustrative Iran explosion scenario"), "located", _stories("demo-iran-explosion", "Iran reported explosion exercise", 35, [(index + 1) / 4 for index in range(35)], IRAN_ANGLES)),
        ("demo-chile-service-restored", "Chile service restoration exercise", "resolved", "low", "geopolitical_infrastructure", _point(-33.05, -71.62, "illustrative Chile service scenario"), "located", _stories("demo-chile-service-restored", "Chile service restoration exercise", 5, [8, 9, 10, 11, 12])),
        ("demo-canada-local-outage", "Canada separate local outage exercise", "developing", "moderate", "geopolitical_infrastructure", _point(49.30, -123.02, "illustrative separate Canada outage scenario"), "located", _stories("demo-canada-local-outage", "separate Canada outage exercise", 3, [2, 26, 120])),
        ("demo-canada-river-watch", "Canada river-watch exercise", "developing", "moderate", "natural_hazard", _point(49.25, -123.10, "illustrative Canada river scenario"), "located", _stories("demo-canada-river-watch", "Canada river-watch exercise", 3, [0.5, 20, 72])),
        ("demo-global-route-bulletin", "Global route bulletin exercise", "reported", "low", "geopolitical_infrastructure", None, "global", _stories("demo-global-route-bulletin", "global route bulletin exercise", 2, [0.75, 90])),
        ("demo-unlocated-software-signal", "Unlocated software signal exercise", "unconfirmed", "unknown", "cybersecurity", None, "unlocated", _stories("demo-unlocated-software-signal", "unlocated software signal exercise", 1, [150])),
    ]
    events = []
    excluded = 0
    for event_id, subject, status, severity, category, location, scope, candidates in scenarios:
        if event_id == "demo-iran-explosion":
            # Duplicate tracked URL, same syndication at another URL, and a transitive duplicate.
            first = candidates[0]
            candidates.extend([
                ArticleCandidate(first.article.model_copy(update={"id": f"{event_id}-duplicate-tracking"}), first.identity_url + "?utm_source=demo#copy"),
                ArticleCandidate(first.article.model_copy(update={"id": f"{event_id}-duplicate-wire", "publisher": "DEMO Mirror Desk"}), "https://fixtures.example.invalid/z-reprint"),
                ArticleCandidate(candidates[1].article.model_copy(update={"id": f"{event_id}-duplicate-second"}), candidates[1].identity_url + "?fbclid=demo"),
            ])
        articles, duplicates = deduplicate_articles(candidates)
        excluded += duplicates
        events.append(NewsEvent(id=event_id, title=f"DEMO {subject}",
                                summary=f"DEMO synthetic {subject}. Status and severity are authored scenario inputs, not a real-world assessment.",
                                category=category, status=status, severity=severity,
                                severity_basis=f"Synthetic scenario assumption: {severity} severity, independent of article count; not a measured real-world impact.",
                                grouping_basis="Explicit hand-authored fixture event association. Nearby positions and shared country names do not merge events.",
                                location=location, scope=scope, is_demo=True, articles=articles))
    return NewsResponse(edition="demo", as_of=DEMO_AS_OF, fetched_at=None, last_attempt_at=None, fetch_state="demo",
                        error=None, events=events, duplicates_excluded=excluded,
                        source_note="All events, publishers, articles, positions and assessments are synthetic DEMO fixtures. The fixed scenario clock anchors time filters. External source URLs are intentionally absent; duplicate fixtures are excluded from coverage counts.")
