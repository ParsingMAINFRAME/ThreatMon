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
        return httpx.Response(200, content=body(page()))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ingest_sources(tmp_path / "news.json", source="wikipedia", client=client, now=NOW)
    asyncio.run(run())
    news = read_sources(tmp_path / "news.json", now=NOW, channel="news")
    status = next(source for source in news.sources if source.source_id == "wikipedia")
    assert status.state == "ok" and status.item_count == 3 and status.kind == "discovery"
    assert sum(event.scope == "located" for event in news.events) == 3
    assert read_sources(tmp_path / "news.json", now=NOW, channel="signals").events == []
