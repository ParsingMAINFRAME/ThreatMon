"""Wikipedia Current events parsing uses synthetic wikitext; no real entries are imported."""

import asyncio
from datetime import UTC, datetime
import json

import httpx
import pytest

from app.news.grouping import group_candidate_events
from app.news.service import NewsError, ingest_sources, read_sources
from app.news.wikipedia import page_title, parse_current_events, request_url

NOW = datetime(2026, 10, 3, 18, tzinfo=UTC)
WIKITEXT = """{{Current events|year=2026|month=10|day=3|top=yes}}
<!-- All news items below this line -->
'''Armed conflicts and attacks'''
*[[Example war (2022–present)|Example war]]
**[[Example strikes on infrastructure]]
***[[Mayor of Kyiv|Kyiv mayor]] reports that forces have struck a bridge in [[Kyiv]], [[Ukraine]]. [https://publisher.example/kyiv-bridge?utm_source=wiki (''Example Independent'')] [https://second.example/story (Second)]
**Unknown gunmen open fire against a vehicle in [[Ras al-Example]], [[Syria]], killing three people.<ref>ignored</ref> [https://agency.example/syria (Example Agency)]
**A repeated citation of the same source. [https://publisher.example/kyiv-bridge (Example Independent)]
**An entry with an unsafe link only. [https://user:secret@unsafe.example/x (Unsafe)]

'''Arts and culture'''
*A festival opens in [[Paris]] after an explosion of interest. [https://arts.example/festival (Arts)]

'''Disasters and accidents'''
*An [[earthquake]] strikes near [[Kabul]], [[Afghanistan]]. [https://quake.example/kabul]
"""


def body(*pages):
    return json.dumps({"batchcomplete": True, "query": {"pages": list(pages)}}).encode()


def page(day=NOW, text=WIKITEXT, **extra):
    record = {"pageid": 1, "ns": 100, "title": page_title(day), **extra}
    if "missing" not in extra:
        record["revisions"] = [{"slots": {"main": {"contentmodel": "wikitext", "content": text}}}]
    return record


def test_request_covers_three_utc_days_in_one_bounded_call():
    url = request_url(NOW)
    assert url.startswith("https://en.wikipedia.org/w/api.php?action=query")
    for day in ("2026%20October%203", "2026%20October%202", "2026%20October%201"):
        assert f"Portal%3ACurrent%20events%2F{day}" in url


def test_entries_keep_wikipedia_attribution_and_first_cited_source():
    events, excluded = parse_current_events(body(page()), retrieved_at=NOW)
    assert excluded == 1
    articles = [event.articles[0] for event in events]
    assert [article.canonical_url for article in articles] == [
        "https://publisher.example/kyiv-bridge", "https://agency.example/syria", "https://quake.example/kabul"]
    first = articles[0]
    assert first.headline == "Kyiv mayor reports that forces have struck a bridge in Kyiv, Ukraine."
    assert first.publisher == "Example Independent" and first.publisher_id == "publisher.example"
    assert first.source_id == "wikipedia" and first.author == "Wikipedia contributors"
    assert first.license_url == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert first.published_at is None and first.first_seen_at == NOW
    assert first.source_window_start == datetime(2026, 10, 3, tzinfo=UTC) and first.source_window_end == NOW
    assert first.observations[0].provider_url == "https://en.wikipedia.org/wiki/Portal:Current_events/2026_October_3"
    assert "not by Example Independent" in first.summary and "CC BY-SA 4.0" in first.summary
    assert articles[2].publisher == "quake.example"
    assert all(event.location is None and event.severity == "unknown" for event in events)
    assert "ignored" not in articles[1].headline and "secret" not in json.dumps([e.model_dump(mode="json") for e in events])


def test_entries_are_placed_by_the_shared_headline_rules():
    events, _ = parse_current_events(body(page()), retrieved_at=NOW)
    placed = {event.articles[0].publisher_id: event for event in group_candidate_events([event.articles[0] for event in events])}
    assert placed["publisher.example"].location.label == "Kyiv, Ukraine (place named in headline)"
    assert placed["publisher.example"].category == "attack"
    assert placed["agency.example"].location.label == "Syria (country named in headline)"
    assert placed["quake.example"].location.label == "Kabul, Afghanistan (place named in headline)"


def test_missing_day_pages_are_skipped_and_other_days_kept():
    events, _ = parse_current_events(body(page(missing=True), page(datetime(2026, 10, 2, tzinfo=UTC))), retrieved_at=NOW)
    assert len(events) == 3
    assert events[0].articles[0].source_window_start == datetime(2026, 10, 2, tzinfo=UTC)
    assert parse_current_events(body(page(missing=True)), retrieved_at=NOW) == ([], 0)


@pytest.mark.parametrize("payload", [
    b"not json", b"{}", body({"title": "Main Page", "revisions": []}), body(page(datetime(2026, 10, 5, tzinfo=UTC))),
    body(page(), page(), page(), page()), b" " * (1024 * 1024 + 1),
], ids=["not-json", "empty-object", "other-page", "future-day", "too-many-pages", "over-1-mib"])
def test_unexpected_responses_fail_the_source(payload):
    with pytest.raises(NewsError):
        parse_current_events(payload, retrieved_at=NOW)


def test_ingest_stores_wikipedia_entries_in_the_news_channel(tmp_path):
    def handler(request):
        assert request.url.host == "en.wikipedia.org" and "ThreatMon" in request.headers["user-agent"]
        if "prop=coordinates" in str(request.url):
            return httpx.Response(200, content=coordinate_body([coordinate_page("Kyiv", 50.45, 30.52, "city")]))
        return httpx.Response(200, content=body(page()))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ingest_sources(tmp_path / "news.json", source="wikipedia", client=client, now=NOW)
    asyncio.run(run())
    news = read_sources(tmp_path / "news.json", now=NOW, channel="news")
    status = next(source for source in news.sources if source.source_id == "wikipedia")
    assert status.state == "ok" and status.error is None and status.item_count == 3 and status.kind == "discovery"
    assert any(event.location and event.location.label == "Kyiv (linked Wikipedia place)" for event in news.events)
    assert sum(event.scope == "located" for event in news.events) == 3
    assert read_sources(tmp_path / "news.json", now=NOW, channel="signals").events == []


TOPIC_WIKITEXT = """'''Armed conflicts and attacks'''
*[[Myanmar civil war (2021–present)|Myanmar civil war]]
**Resistance fighters kill twelve soldiers and seize an outpost. [https://one.example/outpost (One)]
**[[Tatmadaw|Junta]] forces retake a town in [[Sagaing Region]], [[Myanmar]]. [https://two.example/town (Two)]
*[[Israel–Hezbollah conflict]]
**Fighters kill four soldiers in an ambush. [https://three.example/ambush (Three)]
*Militants kill nine villagers in an overnight raid. [https://four.example/raid (Four)]

'''Politics and elections'''
*[[Myanmar civil war]]
**The junta postpones a vote. [https://five.example/vote (Five)]
"""


def topic_events():
    events, _ = parse_current_events(body(page(text=TOPIC_WIKITEXT)), retrieved_at=NOW)
    articles = {event.articles[0].publisher_id: event.articles[0] for event in events}
    return articles, {event.articles[0].publisher_id: event for event in group_candidate_events(list(articles.values()))}


def test_entries_keep_their_section_topic_headings_and_linked_titles():
    articles, _ = topic_events()
    assert articles["one.example"].editor_section == "armed conflicts and attacks"
    assert articles["one.example"].editor_topics == ["Myanmar civil war (2021–present)"]
    assert articles["two.example"].linked_titles == ["Tatmadaw", "Sagaing Region", "Myanmar"]
    assert articles["four.example"].editor_topics == []  # A new top-level bullet ends the previous topic.
    assert articles["five.example"].editor_section == "politics and elections"
    first, _ = parse_current_events(body(page()), retrieved_at=NOW)
    assert first[0].articles[0].editor_topics == ["Example war (2022–present)", "Example strikes on infrastructure"]
    assert first[0].articles[0].linked_titles == ["Mayor of Kyiv", "Kyiv", "Ukraine"]


def test_armed_conflict_section_names_the_event_type_and_a_topic_country_places_unplaced_entries():
    _, placed = topic_events()
    outpost = placed["one.example"]
    assert outpost.category == "attack" and outpost.scope == "located"
    assert outpost.location.label == "Myanmar (country named in topic heading)"
    assert "names no place itself" in outpost.location.basis and outpost.location.confidence == "low"
    # The entry's own text wins over its topic heading.
    assert placed["two.example"].location.label == "Myanmar (country named in headline)"
    # A heading that pairs two parties, or no heading at all, places nothing.
    assert placed["three.example"].category == "attack" and placed["three.example"].scope == "unlocated"
    assert placed["four.example"].category == "attack" and placed["four.example"].scope == "unlocated"
    # Outside the armed-conflict section an entry still needs an incident word.
    assert placed["five.example"].scope == "unlocated" and placed["five.example"].category == "News report"


from app.news.models import LinkedPlace  # noqa: E402
from app.news.wikipedia import add_linked_places, coordinates_url, parse_coordinates  # noqa: E402


def coordinate_body(pages, normalized=(), redirects=()):
    query = {"pages": pages}
    if normalized:
        query["normalized"] = [{"from": a, "to": b} for a, b in normalized]
    if redirects:
        query["redirects"] = [{"from": a, "to": b} for a, b in redirects]
    return json.dumps({"batchcomplete": True, "query": query}).encode()


def coordinate_page(title, lat, lon, kind, **extra):
    return {"pageid": 1, "ns": 0, "title": title, "coordinates": [{"lat": lat, "lon": lon, "primary": True, "globe": "earth", "type": kind, **extra}]}


def test_coordinate_lookup_is_one_bounded_request_per_fifty_titles():
    url = coordinates_url(["Sagaing Region", "Kyiv"])
    assert url.startswith("https://en.wikipedia.org/w/api.php?action=query&prop=coordinates&coprimary=primary")
    assert "colimit=max" in url and "redirects=1" in url and "Sagaing%20Region%7CKyiv" in url


def test_coordinates_follow_redirects_and_keep_only_place_types():
    places = parse_coordinates(coordinate_body([
        coordinate_page("Kyiv", 50.45, 30.5236, "city(2950000)"),
        coordinate_page("Ukraine", 49.0, 32.0, "country"),
        coordinate_page("Dnieper", 46.5, 32.3, "river"),
        coordinate_page("Sagaing Region", 22.0, 95.0, "adm1st"),
        {"pageid": 4, "ns": 0, "title": "Tatmadaw"},
        {"ns": 0, "title": "Missing page", "missing": True},
    ], normalized=[("kyiv", "Kyiv")], redirects=[("Kiev", "Kyiv")]))
    assert set(places) == {"Kyiv", "kyiv", "Kiev", "Sagaing Region"}
    assert places["Kiev"] == LinkedPlace(title="Kyiv", lat=50.45, lon=30.5236, place_type="city", url="https://en.wikipedia.org/wiki/Kyiv")
    assert places["Sagaing Region"].url == "https://en.wikipedia.org/wiki/Sagaing_Region"
    with pytest.raises(NewsError):
        parse_coordinates(b"{}")


def linked_entries(handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            events, _ = parse_current_events(body(page(text=TOPIC_WIKITEXT)), retrieved_at=NOW)
            return await add_linked_places(client, events)
    return asyncio.run(run())


def test_linked_place_coordinates_give_a_finer_position_than_the_country():
    def handler(request):
        assert "prop=coordinates" in str(request.url)
        return httpx.Response(200, content=coordinate_body([
            coordinate_page("Sagaing Region", 22.0, 95.0, "adm1st"), coordinate_page("Myanmar", 21.0, 96.0, "country")]))
    events, warning = linked_entries(handler)
    assert warning is None
    placed = {event.articles[0].publisher_id: event for event in group_candidate_events([event.articles[0] for event in events])}
    town = placed["two.example"]
    assert town.location.label == "Sagaing Region (linked Wikipedia place)"
    assert (town.location.lat, town.location.lon) == (22.0, 95.0)
    assert town.location.source_url == "https://en.wikipedia.org/wiki/Sagaing_Region"
    assert "not a verified incident site" in town.location.basis and town.location.confidence == "low"
    assert placed["one.example"].location.label == "Myanmar (country named in topic heading)"


def test_a_failed_coordinate_lookup_keeps_entries_and_says_why():
    events, warning = linked_entries(lambda request: httpx.Response(503))
    assert len(events) == 5 and all(not event.articles[0].linked_places for event in events)
    assert warning == "Wikipedia coordinate lookup returned HTTP 503; entries kept without linked place coordinates"


def linked(title, lat, lon, kind="city"):
    return LinkedPlace(title=title, lat=lat, lon=lon, place_type=kind, url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")


@pytest.mark.parametrize("headline,places,label", [
    # One linked town the gazetteer does not know.
    ("Drones strike an oil depot in Liski, Russia.", [linked("Liski", 50.98, 39.5)], "Liski (linked Wikipedia place)"),
    # A named attack article carries its own coordinate and outranks the town it happened in.
    ("A bombing at a market kills nine in Quetta.", [linked("2026 Quetta market bombing", 30.19, 67.01, "event"), linked("Quetta", 30.18, 67.0)],
     "2026 Quetta market bombing (linked Wikipedia place)"),
    # A region link beats a city read from the link's display text ("Kharkiv region").
    ("Shelling hits villages in the Kharkiv region.", [linked("Kharkiv Oblast", 49.5, 36.5, "adm1st")], "Kharkiv Oblast (linked Wikipedia place)"),
    # Two peer towns, or a town far from the city the text names, leave the text rules in charge.
    ("Missiles launched from Belgorod strike Kharkiv.", [linked("Belgorod", 50.6, 36.59), linked("Kharkiv", 49.99, 36.23)],
     "Kharkiv, Ukraine (place named in headline)"),
    ("A drone attack hits Moscow.", [linked("Vladivostok", 43.1, 131.9)], "Moscow, Russia (place named in headline)"),
])
def test_linked_place_rules(headline, places, label):
    article = parse_current_events(body(page()), retrieved_at=NOW)[0][0].articles[0].model_copy(
        update={"headline": headline, "linked_places": places, "editor_topics": []})
    assert group_candidate_events([article])[0].location.label == label
