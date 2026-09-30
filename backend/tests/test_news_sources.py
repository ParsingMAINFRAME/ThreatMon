import asyncio
from datetime import UTC, datetime, timedelta
import json

import httpx
import pytest

from app.news.models import NewsResponse
from app.news.service import ingest_sources, read_sources, source_cache_path

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def feed(host):
    return (f'<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>'
            f'<title>Published headline</title><link>https://{host}/story/</link>'
            '<pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate><dc:creator>Writer</dc:creator>'
            '</item></channel></rss>').encode()


def ingest(path, handler, now=NOW, source="all"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ingest_sources(path, source=source, client=client, now=now)
    return asyncio.run(run())


def test_cache_paths_preserve_legacy_nasa_and_do_not_collide(tmp_path):
    base = tmp_path / "selected.json"
    assert source_cache_path(base, "nasa") == base
    assert source_cache_path(base, "globalvoices") == tmp_path / "selected.globalvoices.json"
    assert source_cache_path(base, "gdacs") == tmp_path / "selected.gdacs.json"
    with pytest.raises(ValueError):
        source_cache_path(base, "../../unsafe")


def test_missing_sources_are_read_only_and_have_independent_status(tmp_path):
    result = read_sources(tmp_path / "absent.json", now=NOW, channel="all")
    assert result.fetch_state == "never_fetched" and result.events == []
    assert {source.source_id for source in result.sources} == {"nasa", "globalvoices", "gdelt", "gdacs"}
    assert all(source.state == "never_fetched" and source.last_success_at is None for source in result.sources)
    assert list(tmp_path.iterdir()) == []


def test_independent_failure_preserves_other_source_and_partial_truth(tmp_path):
    base = tmp_path / "news.json"
    calls = []
    def first(request):
        calls.append(request)
        if request.url.host == "www.nasa.gov":
            return httpx.Response(200, content=feed("www.nasa.gov"))
        if request.url.host == "globalvoices.org":
            return httpx.Response(200, content=feed("globalvoices.org"), headers={"ETag": '"gv-1"'})
        return httpx.Response(503, headers={"Retry-After": "3600"})
    good = ingest(base, first)
    assert len(calls) == 4 and good.fetch_state == "partial" and len(good.events) == 2
    assert good.fetched_at == NOW
    by_source = {item.source_id: item for item in good.sources}
    assert by_source["gdacs"].state == "error" and by_source["gdacs"].next_fetch_at == NOW + timedelta(hours=1)
    assert by_source["globalvoices"].next_fetch_at == NOW + timedelta(minutes=15)
    later = NOW + timedelta(minutes=16)
    failed = ingest(base, lambda request: httpx.Response(403), later, source="globalvoices")
    assert failed.fetch_state == "partial" and len(failed.events) == 2
    status = next(item for item in failed.sources if item.source_id == "globalvoices")
    assert status.state == "error" and status.last_success_at == NOW and status.last_attempt_at == later
    assert read_sources(base, now=later, channel="all").events == failed.events


def test_new_source_cooldown_conditional_and_304_keeps_article_retrieval(tmp_path):
    base = tmp_path / "news.json"
    first = ingest(base, lambda request: httpx.Response(200, content=feed("globalvoices.org"),
                   headers={"ETag": '"one"', "Last-Modified": "Wed, 30 Sep 2026 10:00:00 GMT"}), source="globalvoices")
    ingest(base, lambda request: pytest.fail("must respect 15 minute interval"), NOW + timedelta(minutes=14), source="globalvoices")
    def unchanged(request):
        assert request.headers["If-None-Match"] == '"one"'
        assert request.headers["If-Modified-Since"] == "Wed, 30 Sep 2026 10:00:00 GMT"
        return httpx.Response(304, headers={"Cache-Control": "max-age=1800"})
    result = ingest(base, unchanged, NOW + timedelta(minutes=15), source="globalvoices")
    status = next(item for item in result.sources if item.source_id == "globalvoices")
    assert status.last_success_at == NOW + timedelta(minutes=15)
    assert status.next_fetch_at == NOW + timedelta(minutes=45)
    assert result.events[0].articles[0].retrieved_at == first.events[0].articles[0].retrieved_at == NOW


def test_legacy_nasa_cache_gets_additive_defaults_and_source_health(tmp_path):
    base = tmp_path / "news.json"
    ingest(base, lambda request: httpx.Response(200, content=feed("www.nasa.gov")), source="nasa")
    legacy = json.loads(base.read_text())
    legacy["response"].pop("sources", None)
    for event in legacy["response"]["events"]:
        event.pop("source_event_id", None)
        event.pop("source_alert_level", None)
        for article in event["articles"]:
            for key in ["source_id", "publisher_id", "record_kind", "author", "license_url", "source_window_start", "source_window_end"]:
                article.pop(key, None)
    base.write_text(json.dumps(legacy))
    result = read_sources(base, now=NOW, channel="all")
    assert result.fetch_state == "partial" and result.events[0].articles[0].source_id == "nasa"
    assert NewsResponse.model_validate_json(result.model_dump_json()) == result


def test_corrupt_feed_cache_does_not_hide_good_other_feed(tmp_path):
    base = tmp_path / "news.json"
    ingest(base, lambda request: httpx.Response(200, content=feed("www.nasa.gov")), source="nasa")
    source_cache_path(base, "gdacs").write_text("invalid")
    result = read_sources(base, now=NOW, channel="all")
    assert result.fetch_state == "partial" and len(result.events) == 1
    assert next(item for item in result.sources if item.source_id == "gdacs").state == "error"
