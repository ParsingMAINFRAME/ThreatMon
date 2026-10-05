"""Placement report: how many stored events the map can show, and on what evidence.

Counts describe the stored sample only. They measure where markers come from, not
whether any marker is right; that needs analyst review of the sources.
"""

from collections import Counter
import re

from app.news.models import NewsResponse

# The parenthesised suffix every automatic or reviewed news position carries.
BASIS_LABELS = {
    "linked Wikipedia place": "linked_place",
    "place named in headline": "headline_city",
    "country named in headline": "headline_country",
    "country named in topic heading": "topic_country",
    "analyst-set position": "analyst_set",
}


def placement_basis(label: str) -> str:
    match = re.search(r"\(([^()]*)\)\s*$", label)
    return BASIS_LABELS.get(match[1], "source_point") if match else "source_point"


def placement_report(response: NewsResponse) -> dict:
    events = response.events
    by_source: dict[str, Counter] = {}
    basis: Counter = Counter()
    for event in events:
        source = event.articles[0].source_id or "unknown"
        counts = by_source.setdefault(source, Counter())
        counts[event.scope] += 1
        if event.location is not None:
            basis[placement_basis(event.location.label)] += 1
    located = sum(event.scope == "located" for event in events)
    return {
        "as_of": response.as_of.isoformat(),
        "events": len(events),
        "located": located,
        "unlocated": sum(event.scope == "unlocated" for event in events),
        "global": sum(event.scope == "global" for event in events),
        "located_share": round(located / len(events), 3) if events else None,
        "position_basis": dict(sorted(basis.items())),
        "confidence": dict(sorted(Counter(event.location.confidence for event in events if event.location).items())),
        "analyst_reviews": dict(sorted(Counter(event.placement_review.action for event in events if event.placement_review).items())),
        "by_first_source": {source: {scope: counts[scope] for scope in ("located", "unlocated", "global")}
                            for source, counts in sorted(by_source.items())},
        "attack_events": {"located": sum(event.category == "attack" and event.scope == "located" for event in events),
                          "unlocated": sum(event.category == "attack" and event.scope == "unlocated" for event in events)},
        "note": "Counts describe this stored sample and where markers come from, not whether they are correct.",
    }
