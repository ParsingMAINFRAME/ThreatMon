"""Synthetic headlines test grouping policy; none are imported as actual news."""

from datetime import UTC, datetime, timedelta

import pytest

from app.news.grouping import GROUPING_VERSION, group_candidate_events
from app.news.models import NewsArticle, NewsObservation


NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
FIRST = "Explosion at Orion chemical plant in Tehran"
SECOND = "Tehran blast damages Orion chemical facility"


def article(identity, headline=FIRST, *, publisher=None, hours=0, published=True, observed=True):
    publisher = publisher or f"publisher-{identity}.example"
    return NewsArticle(
        id=identity, canonical_url=f"https://{publisher}/{identity}", headline=headline,
        publisher=publisher, publisher_id=publisher, source_id="gdelt", record_kind="article",
        published_at=NOW + timedelta(hours=hours) if published else None,
        first_seen_at=NOW + timedelta(hours=hours) if observed else None,
        retrieved_at=NOW + timedelta(days=2), summary="Synthetic test metadata.", is_demo=False,
    )


def test_compatible_cross_publisher_headlines_form_candidate_at_named_place():
    records = [article("a"), article("b", SECOND)]
    before = [item.model_dump() for item in records]
    events = group_candidate_events(records)
    assert len(events) == 1
    event = events[0]
    assert event.grouping_status == "candidate"
    assert event.grouping_version == GROUPING_VERSION
    assert event.assignment_revision
    assert event.place_hints == ["Tehran"]
    assert event.scope == "located" and event.location.label == "Tehran, Iran (place named in headline)"
    assert event.location.precision == "approximate_area" and event.location.confidence == "low"
    assert "not a verified incident site" in event.location.basis
    assert event.severity == "unknown" and event.status == "unconfirmed"
    assert {item.id for item in event.articles} == {"a", "b"}
    assert "independent confirmation" in event.grouping_basis.lower()
    assert [item.model_dump() for item in records] == before


def test_same_city_and_incident_type_join_without_shared_names():
    events = group_candidate_events([article("a", "Ukraine bombs Moscow in overnight raid"), article("b", "Drone attack on Moscow, mayor says")])
    assert len(events) == 1 and events[0].category == "attack" and len(events[0].articles) == 2
    assert events[0].location.label == "Moscow, Russia (place named in headline)"
    assert (events[0].location.lat, events[0].location.lon) == (55.76, 37.62)


@pytest.mark.parametrize("headline,label,point", [
    ("Bomb blast kills three in Saudi Arabia", "Saudi Arabia (country named in headline)", (24.0, 44.5)),
    ("Russia strikes Ukraine with missiles", "Ukraine (country named in headline)", (49.0, 31.4)),
    ("Kyiv says Russian missiles hit Kharkiv", "Kharkiv, Ukraine (place named in headline)", (49.99, 36.23)),
    ("Explosion reported in Tripoli, Libya", "Tripoli, Libya (place named in headline)", (32.89, 13.19)),
    ("Blast heard in Kiev", "Kyiv, Ukraine (place named in headline)", (50.45, 30.52)),
    ("Gunmen open fire on villagers in Marte, Borno State, Nigeria", "Nigeria (country named in headline)", (9.6, 8.1)),
])
def test_single_headline_is_placed_at_the_named_place_with_low_confidence(headline, label, point):
    event = group_candidate_events([article("a", headline)])[0]
    assert event.grouping_status == "single_source" and event.scope == "located"
    assert event.location.label == label and (event.location.lat, event.location.lon) == point
    assert event.location.precision == "approximate_area" and event.location.confidence == "low"
    assert event.location.source_url == event.articles[0].canonical_url
    assert event.severity == "unknown"


def test_country_marker_is_a_rough_centre_and_never_the_capital():
    event = group_candidate_events([article("a", "Bomb blast kills three in Saudi Arabia")])[0]
    assert (event.location.lat, event.location.lon) != (24.71, 46.68)  # Riyadh
    assert "not its capital" in event.location.basis


@pytest.mark.parametrize("headline", [
    "Orion chemical plant quarterly results beat forecasts in Tehran",  # no incident word
    "Explosion at Orion chemical plant",  # no place
    "Explosion at Orion chemical plant in Unknownville",  # place outside the vocabulary
    "Explosion at Orion chemical plant in Tripoli",  # ambiguous city
    "Paris, Texas blast damages Orion chemical facility",  # explicit other Paris
    "Tehran and Beirut report Orion chemical plant explosion",  # two cities, neither targeted
    "Iran and Israel trade attacks",  # two countries, neither targeted
    "Anniversary of Orion chemical plant explosion in Tehran",  # historical
    "Experts warn of risk of attack in London",  # speculative
    "Georgia homecoming party shooting: 2 dead in Vienna",  # a US state signals a same-name town
    "Rail strike halts trains in Paris",  # labour dispute
    "Minister under fire in London over budget",  # figure of speech
    "Heart attack deaths rise in India",  # medical
    "Flooding forces evacuations across New Mexico",  # a place whose name contains another place
    "New York Times reporter describes shooting",  # publication name, not a place
    "Pilot on flight to Israel stabbed colleague and tried to crash plane",  # destination, not a targeted place
    "Morocco strike late to win Africa title",  # sport
    "Blast kills two | Kabul Daily",  # trailing publisher name
])
def test_headlines_without_one_clear_place_and_incident_stay_unlocated(headline):
    event = group_candidate_events([article("a", headline)])[0]
    assert event.location is None and event.scope == "unlocated"


@pytest.mark.parametrize("first,second", [
    (FIRST, "Fire at Orion chemical plant in Tehran"),
    (FIRST, "Explosion at Orion chemical plant in Beirut"),
    (FIRST, "Tehran and Beirut report Orion chemical plant explosion"),
    (FIRST, "Anniversary of Orion chemical plant explosion in Tehran"),
    ("Explosion at Orion chemical plant in Unknownville", "Unknownville blast damages Orion chemical plant"),
    ("Explosion at Orion chemical plant in Tripoli", "Tripoli blast damages Orion chemical facility"),
    ("Explosion at Orion chemical plant in Paris, France", "Paris, Texas blast damages Orion chemical facility"),
    ("Explosion at Orion chemical plant in Iran", "Blast in Iran injures market traders"),
])
def test_different_ambiguous_or_conflicting_place_and_type_clues_do_not_join(first, second):
    events = group_candidate_events([article("a", first), article("b", second)])
    assert len(events) == 2
    assert all(event.grouping_status == "single_source" for event in events)


def test_country_level_reports_join_only_with_shared_headline_content():
    events = group_candidate_events([
        article("a", "Explosion at Orion chemical plant in Iran"), article("b", "Iran blast damages Orion chemical facility")])
    assert len(events) == 1 and events[0].location.label == "Iran (country named in headline)"

@pytest.mark.parametrize("first_date,second_date", [
    ("on 2026-09-29", "on 2026-09-30"),
    ("on September 29", "on September 30"),
    ("on Tuesday", "on Wednesday"),
    ("in 2025", "in 2026"),
])
def test_conflicting_explicit_dates_are_not_related(first_date, second_date):
    assert len(group_candidate_events([
        article("a", f"{FIRST} {first_date}"), article("b", f"{SECOND} {second_date}"),
    ])) == 2


def test_different_spellings_of_same_date_and_explicit_tripoli_country_can_match():
    events = group_candidate_events([
        article("a", "Explosion at Orion chemical plant in Tripoli, Libya on September 30"),
        article("b", "Tripoli, Libya blast damages Orion chemical facility on 30 September"),
    ])
    assert len(events) == 1 and events[0].place_hints == ["Tripoli, Libya"]


def test_conflicting_tripoli_countries_are_not_related():
    assert len(group_candidate_events([
        article("a", "Explosion at Orion chemical plant in Tripoli, Libya"),
        article("b", "Tripoli, Lebanon blast damages Orion chemical facility"),
    ])) == 2


def test_time_limit_and_complete_link_prevent_transitive_chaining():
    events = group_candidate_events([article("a", hours=0), article("b", SECOND, hours=20), article("c", hours=40)])
    assert sorted(len(event.articles) for event in events) == [1, 2]
    assert {item.id for event in events for item in event.articles} == {"a", "b", "c"}
    assert len(group_candidate_events([article("a"), article("b", SECOND, hours=24)])) == 1
    assert len(group_candidate_events([article("a"), article("b", SECOND, hours=24.01)])) == 2


def test_collection_time_is_an_explicit_heuristic_without_inventing_publication():
    events = group_candidate_events([article("a", published=False), article("b", SECOND, published=False)])
    assert len(events) == 1
    assert all(item.published_at is None for item in events[0].articles)
    assert "collection times are only heuristics" in events[0].grouping_basis.lower()
    assert len(group_candidate_events([
        article("a", published=False).model_copy(update={"first_seen_at": None}),
        article("b", SECOND, published=False).model_copy(update={"first_seen_at": None}),
    ])) == 2  # Retrieval time alone is not evidence that two reports concern the same recent event.


def test_multiple_reports_from_one_publisher_do_not_create_cross_publisher_candidate():
    events = group_candidate_events([article("a", publisher="one.example"), article("b", SECOND, publisher="one.example")])
    assert len(events) == 2 and all(len(event.articles) == 1 for event in events)


def test_equal_headlines_keep_collected_links_but_never_claim_independent_confirmation():
    event = group_candidate_events([article("a"), article("b")])[0]
    assert len(event.articles) == 2
    assert len({item.canonical_url for item in event.articles}) == 2
    assert "shared copy" in event.grouping_basis.lower()
    assert "not independent confirmation" in event.grouping_basis.lower()


def test_canonical_identity_boundaries_and_empty_input():
    first = article("a")
    assert len(group_candidate_events([first, first.model_copy(deep=True)])) == 1
    with pytest.raises(ValueError, match="identity"):
        group_candidate_events([first, article("a", SECOND)])
    with pytest.raises(ValueError, match="canonical"):
        group_candidate_events([first, first.model_copy(update={"id": "b"})])
    assert group_candidate_events([]) == []


def test_only_actual_publisher_articles_are_grouped():
    with pytest.raises(ValueError, match="publisher articles"):
        group_candidate_events([article("a").model_copy(update={"record_kind": "official_report"})])
    with pytest.raises(ValueError, match="publisher articles"):
        group_candidate_events([article("a").model_copy(update={"is_demo": True})])


def test_assignments_are_order_independent_and_revision_tracks_evidence():
    records = [article("a"), article("b", SECOND), article("c", "A separate publication")]
    first = group_candidate_events(records)
    reversed_events = group_candidate_events(list(reversed(records)))
    assert [item.model_dump() for item in first] == [item.model_dump() for item in reversed_events]
    grouped = next(event for event in first if event.grouping_status == "candidate")
    changed = group_candidate_events([article("a"), article("b", SECOND + " after evacuation")])
    assert changed[0].assignment_revision != grouped.assignment_revision


def test_previous_candidate_identity_survives_growth_but_not_incompatible_merger():
    previous = group_candidate_events([article("a"), article("b", SECOND)])
    current = group_candidate_events([article("a"), article("b", SECOND), article("c", FIRST)], previous_events=previous)
    assert current[0].id == previous[0].id
    assert current[0].assignment_revision != previous[0].assignment_revision
    # A previous assignment never overrides today's explicit geographic contradiction.
    split = group_candidate_events([article("a"), article("b", SECOND.replace("Tehran", "Beirut"))], previous_events=previous)
    assert len(split) == 2 and all(event.grouping_status == "single_source" for event in split)


def test_input_and_event_bounds_preserve_union_without_overlong_groups():
    records = [article(str(index)) for index in range(260)]
    events = group_candidate_events(records)
    assert sorted(len(event.articles) for event in events) == [10, 250]
    assert sum(len(event.articles) for event in events) == 260
    assert len({item.id for event in events for item in event.articles}) == 260
    assert len(group_candidate_events(records[:250])[0].articles) == 250


def observation(*, hours=0, language="English", country="France"):
    return NewsObservation(provider_id="gdelt", provider_url="https://api.gdeltproject.org/api/v2/doc/doc",
                           provider_timestamp=NOW + timedelta(hours=hours), retrieved_at=NOW + timedelta(days=2),
                           provider_timestamp_raw=(NOW + timedelta(hours=hours)).isoformat(),
                           language=language, source_country=country)


def test_provider_clock_is_only_a_window_heuristic_and_source_country_is_not_incident_geography():
    first = article("a", published=False).model_copy(update={"observations": [observation(country="France")]})
    second = article("b", SECOND, published=False).model_copy(update={"observations": [observation(country="Germany")]})
    event = group_candidate_events([first, second])[0]
    assert len(event.articles) == 2 and event.place_hints == ["Tehran"]
    assert event.location.label.startswith("Tehran, Iran")  # never France or Germany, the outlets' countries
    assert "provider and collection times are only heuristics" in event.grouping_basis.lower()
    later = second.model_copy(update={"observations": [observation(hours=25)]})
    assert len(group_candidate_events([first, later])) == 2


def test_conflicting_provider_clocks_or_non_english_metadata_prevent_heuristic_association():
    first = article("a", published=False).model_copy(update={"observations": [observation(), observation(hours=25)]})
    assert len(group_candidate_events([first, article("b", SECOND)])) == 2
    foreign = article("a").model_copy(update={"observations": [observation(language="Spanish")]})
    assert len(group_candidate_events([foreign, article("b", SECOND)])) == 2


def test_country_adjectives_alone_do_not_place_a_headline():
    event = group_candidate_events([article("a", "Explosion damages Iranian chemical facility")])[0]
    assert event.location is None and event.place_hints == []

def test_prior_algorithm_version_cannot_reuse_an_old_assignment_identity():
    records = [article("a"), article("b", SECOND)]
    previous = group_candidate_events(records)[0].model_copy(update={"id": "old-version-id", "grouping_version": "obsolete"})
    assert group_candidate_events(records, previous_events=[previous])[0].id != "old-version-id"


def test_input_bound_rejects_unbounded_computation_before_processing_articles():
    with pytest.raises(ValueError, match="1000 article bound"):
        group_candidate_events([article("a")] * 1001)
