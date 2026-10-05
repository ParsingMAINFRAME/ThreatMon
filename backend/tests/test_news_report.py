"""Placement report over a synthetic Current events sample (tests/fixtures; invented entries)."""

import asyncio
import json
from pathlib import Path

import httpx

from app.cli import main
from app.news.grouping import group_candidate_events
from app.news.models import NewsResponse
from app.news.report import placement_basis, placement_report
from app.news.service import ingest_sources
from app.news.wikipedia import parse_current_events
from tests.test_news_wikipedia import NOW, body, page

FIXTURES = Path(__file__).parent / "fixtures"
WIKITEXT = (FIXTURES / "wikipedia_current_events_sample.wikitext").read_text()
COORDINATES = (FIXTURES / "wikipedia_coordinates_sample.json").read_bytes()


def handler(request):
    return httpx.Response(200, content=COORDINATES if "prop=coordinates" in str(request.url) else body(page(text=WIKITEXT)))


def ingest(path):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await ingest_sources(path, source="wikipedia", client=client, now=NOW)
    asyncio.run(run())


def report_for(articles):
    events = group_candidate_events(articles)
    return placement_report(NewsResponse(edition="snapshot", as_of=NOW, fetched_at=NOW, last_attempt_at=NOW, fetch_state="ok",
                                         events=events, source_note="Synthetic sample."))


def test_basis_is_read_from_the_position_label():
    assert placement_basis("Liski (linked Wikipedia place)") == "linked_place"
    assert placement_basis("Myanmar (country named in topic heading)") == "topic_country"
    assert placement_basis("M 5.1 - 10 km N of Example") == "source_point"


def test_editor_context_places_more_of_the_sample_without_placing_figurative_entries():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            from app.news.wikipedia import add_linked_places
            return await add_linked_places(client, parse_current_events(body(page(text=WIKITEXT)), retrieved_at=NOW)[0])
    events, warning = asyncio.run(run())
    assert warning is None and len(events) == 20
    articles = [event.articles[0] for event in events]
    headline_only = report_for([article.model_copy(update={"editor_section": None, "editor_topics": [], "linked_places": []})
                                for article in articles])
    full = report_for(articles)
    # Headline rules alone place 7 of 19 events (two Kharkiv headlines form one candidate group).
    assert (headline_only["events"], headline_only["located"]) == (19, 7)
    assert (full["events"], full["located"]) == (20, 15)
    assert full["position_basis"] == {"headline_city": 1, "headline_country": 2, "linked_place": 9, "topic_country": 3}
    assert full["attack_events"] == {"located": 9, "unlocated": 1}
    placed = {article.canonical_url.rsplit("/", 1)[1]: event for event in group_candidate_events(articles) for article in event.articles}
    assert placed["a2"].location.label == "Kharkiv Oblast (linked Wikipedia place)"
    assert placed["a3"].location.label == "Liski (linked Wikipedia place)"  # Not Voronezh city, read from "Voronezh Oblast".
    assert placed["a7"].location.label == "Myanmar (country named in topic heading)"
    assert placed["a12"].location.label == "Kharkiv, Ukraine (place named in headline)"
    assert placed["a15"].scope == "unlocated"  # A lake's single coordinate is not used.
    for figurative in ("a19", "a20"):
        assert placed[figurative].scope == "unlocated"


def test_cli_prints_the_report_for_the_stored_snapshot(tmp_path, capsys):
    path = tmp_path / "news.json"
    ingest(path)
    assert main(["news", "report", "--cache-path", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["events"] == 20 and report["located"] == 15 and report["located_share"] == 0.75
    assert report["by_first_source"] == {"wikipedia": {"located": 15, "unlocated": 5, "global": 0}}
    assert "not whether they are correct" in report["note"]
