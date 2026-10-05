"""Analyst placement reviews over a synthetic stored Wikipedia snapshot."""

import asyncio
import json

import httpx
import pytest

from app.cli import main
from app.news.review import load_reviews, reviews_path
from app.news.service import ingest_sources, read_sources
from tests.test_news_wikipedia import NOW, body, page

KYIV = "https://publisher.example/kyiv-bridge"
SYRIA = "https://agency.example/syria"


@pytest.fixture
def stored(tmp_path):
    path = tmp_path / "news.json"

    async def run():
        handler = lambda request: httpx.Response(200, content=json.dumps({"query": {"pages": []}}).encode()) \
            if "prop=coordinates" in str(request.url) else httpx.Response(200, content=body(page()))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await ingest_sources(path, source="wikipedia", client=client, now=NOW)
    asyncio.run(run())
    return path


def event_for(path, url):
    return next(event for event in read_sources(path, channel="news").events if any(a.canonical_url == url for a in event.articles))


def review(path, *args, capsys):
    code = main(["news", "review", "--cache-path", str(path), *args])
    return code, json.loads(capsys.readouterr().out)


def test_moving_a_position_replaces_the_automatic_one_with_a_labeled_analyst_position(stored, capsys):
    before = event_for(stored, SYRIA)
    assert before.location.label == "Syria (country named in headline)"
    code, output = review(stored, "--url", SYRIA, "--move", "35.93", "36.63", "--label", "Idlib, Syria",
                          "--note", "The cited report names Idlib.", "--reviewer", "Ryan", capsys=capsys)
    assert code == 0 and output["review"]["action"] == "moved"
    after = event_for(stored, SYRIA)
    assert after.location.label == "Idlib, Syria (analyst-set position)"
    assert (after.location.lat, after.location.lon) == (35.93, 36.63)
    assert after.location.confidence == "medium" and "analyst judgement" in after.location.basis
    assert after.placement_review.reviewer == "Ryan" and after.placement_review.note == "The cited report names Idlib."
    assert reviews_path(stored).name == "news.placement-reviews.json"


def test_removing_a_position_unlocates_the_event(stored, capsys):
    code, _ = review(stored, "--url", KYIV, "--remove", "--note", "Bridge is outside the city.", "--reviewer", "Ryan", capsys=capsys)
    after = event_for(stored, KYIV)
    assert code == 0 and after.scope == "unlocated" and after.location is None and after.placement_review.action == "removed"


def test_a_confirmation_raises_confidence_only_while_the_position_is_unchanged(stored, capsys):
    code, _ = review(stored, "--url", KYIV, "--confirm", "--note", "Matches the cited report.", "--reviewer", "Ryan", capsys=capsys)
    after = event_for(stored, KYIV)
    assert code == 0 and after.location.confidence == "medium" and after.placement_review.action == "confirmed"
    assert "checked this position" in after.location.basis
    reviews = load_reviews(stored)
    stale = reviews[KYIV].model_copy(update={"reviewed_label": "Lviv, Ukraine (place named in headline)"})
    from app.news.review import save_reviews
    save_reviews(stored, {KYIV: stale})
    lapsed = event_for(stored, KYIV)
    assert lapsed.location.confidence == "low" and lapsed.placement_review is None


def test_clear_and_list(stored, capsys):
    review(stored, "--url", KYIV, "--remove", "--note", "n", "--reviewer", "r", capsys=capsys)
    code, listed = review(stored, "--list", capsys=capsys)
    assert code == 0 and [item["article_url"] for item in listed] == [KYIV]
    code, output = review(stored, "--url", KYIV, "--clear", capsys=capsys)
    assert code == 0 and output == {"cleared": KYIV}
    assert event_for(stored, KYIV).location is not None


@pytest.mark.parametrize("args", [
    ["--url", "https://nowhere.example/x", "--remove", "--note", "n", "--reviewer", "r"],
    ["--url", KYIV, "--remove", "--note", "n"],
    ["--url", KYIV, "--move", "1", "2", "--note", "n", "--reviewer", "r"],
    ["--url", KYIV, "--remove", "--label", "X", "--note", "n", "--reviewer", "r"],
    ["--url", KYIV, "--note", "n", "--reviewer", "r"],
    ["--url", "javascript:alert(1)", "--remove", "--note", "n", "--reviewer", "r"],
])
def test_incomplete_or_unknown_reviews_are_refused(stored, args):
    with pytest.raises(SystemExit):
        main(["news", "review", "--cache-path", str(stored), *args])
    assert not reviews_path(stored).exists()


def test_out_of_range_coordinates_are_refused(stored, capsys):
    code, output = review(stored, "--url", KYIV, "--move", "95", "2", "--label", "X", "--note", "n", "--reviewer", "r", capsys=capsys)
    assert code == 1 and "less than or equal to 90" in output["error"]


def test_an_unreadable_review_file_leaves_automatic_positions_and_says_so(stored):
    reviews_path(stored).write_text("not json")
    news = read_sources(stored, channel="news")
    assert "analyst reviews not applied" in news.error
    assert event_for(stored, KYIV).location.label == "Kyiv, Ukraine (place named in headline)"
