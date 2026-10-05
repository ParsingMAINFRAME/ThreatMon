import asyncio
from datetime import UTC, datetime, timedelta
import json

import httpx
import pytest

from app.news.service import NewsCache, ingest_news, read_sources, source_cache_path

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def payload(count=1):
    return {"articles": [{"url": f"https://publisher.example/story?id={i}", "title": f"Publisher article {i}",
                          "seendate": "20260930T100000Z", "language": "English", "sourcecountry": "France"}
                         for i in range(count)]}


def ingest(path, handler, now=NOW):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ingest_news(path, source="gdelt", client=client, now=now)
    return asyncio.run(run())


def stored(path):
    return NewsCache.model_validate_json(source_cache_path(path, "gdelt").read_bytes())


def test_gdelt_one_request_retry_after_and_persisted_failure_cooldown(tmp_path):
    path = tmp_path / "news.json"
    calls = []
    def busy(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"}, text="private response")
    result = ingest(path, busy)
    assert len(calls) == 1 and result.fetch_state == "error"
    assert "private response" not in result.error
    assert stored(path).next_fetch_at == NOW + timedelta(hours=1)
    assert stored(path).query_watermark is None
    ingest(path, lambda request: pytest.fail("must honor persisted backoff"), NOW + timedelta(minutes=59))


def test_gdelt_fixed_request_success_watermark_overlap_and_preserved_first_collection(tmp_path):
    path = tmp_path / "news.json"
    calls = []
    def ok(request):
        calls.append(request)
        return httpx.Response(200, json=payload())
    first = ingest(path, ok)
    assert first.fetch_state == "ok" and len(calls) == 1
    request = calls[0]
    assert request.method == "GET" and request.url.host == "api.gdeltproject.org"
    assert request.url.path == "/api/v2/doc/doc"
    assert request.url.params["mode"] == "ArtList" and request.url.params["maxrecords"] == "250"
    assert request.url.params["startdatetime"] == "20260929120000"
    assert request.url.params["enddatetime"] == "20260930120000"
    assert "sourcelang:english" in request.url.params["query"]
    ingest(path, lambda request: pytest.fail("must honor 15 minute cooldown"), NOW + timedelta(minutes=14))
    revised = ingest(path, ok, NOW + timedelta(minutes=15))
    assert calls[-1].url.params["startdatetime"] == "20260930114500"
    article = revised.events[0].articles[0]
    assert article.published_at is None and article.first_seen_at == NOW
    assert article.retrieved_at == NOW + timedelta(minutes=15)
    assert len(article.observations) == 1
    assert stored(path).query_watermark == NOW + timedelta(minutes=15)


def test_failure_preserves_good_articles_and_does_not_advance_query_watermark(tmp_path):
    path = tmp_path / "news.json"
    first = ingest(path, lambda request: httpx.Response(200, json=payload()))
    failed = ingest(path, lambda request: httpx.Response(503), NOW + timedelta(minutes=15))
    assert failed.fetch_state == "error" and failed.events == first.events
    assert failed.fetched_at == NOW and stored(path).query_watermark == NOW
    calls = []
    def ok(request):
        calls.append(request)
        return httpx.Response(200, json={"articles": []})
    ingest(path, ok, NOW + timedelta(minutes=30))
    assert calls[0].url.params["startdatetime"] == "20260930114500"


def test_cap_flag_persists_and_retention_uses_first_collection_not_retrieval(tmp_path):
    path = tmp_path / "news.json"
    first = ingest(path, lambda request: httpx.Response(200, json=payload(250)))
    assert len(first.events) == 250 and first.sources[0].possibly_truncated
    second = ingest(path, lambda request: httpx.Response(200, json=payload(1)), NOW + timedelta(days=6))
    assert len(second.events) == 250 and second.sources[0].possibly_truncated
    assert all(event.articles[0].first_seen_at == NOW for event in second.events)
    expired = ingest(path, lambda request: httpx.Response(200, json=payload(1)), NOW + timedelta(days=7, seconds=1))
    assert expired.events == [] and expired.sources[0].possibly_truncated


@pytest.mark.parametrize("response", [httpx.Response(302, headers={"Location": "http://localhost/private"}),
                                      httpx.Response(200, content=b"<html>Service error</html>"),
                                      httpx.Response(200, content=b"x" * (1024 * 1024 + 1))])
def test_redirect_and_invalid_responses_make_one_request_and_preserve_cache(tmp_path, response):
    path = tmp_path / "news.json"
    first = ingest(path, lambda request: httpx.Response(200, json=payload()))
    calls = []
    def bad(request):
        calls.append(request)
        return response
    result = ingest(path, bad, NOW + timedelta(minutes=15))
    assert len(calls) == 1 and result.fetch_state == "error" and result.events == first.events


def test_changed_query_starts_new_window_without_claiming_failed_progress(tmp_path, monkeypatch):
    from app.core.config import get_settings
    path = tmp_path / "news.json"
    ingest(path, lambda request: httpx.Response(200, json=payload()))
    monkeypatch.setattr(get_settings(), "news_gdelt_query", "flood sourcelang:english")
    ingest(path, lambda request: httpx.Response(503), NOW + timedelta(hours=2))
    assert stored(path).query_watermark == NOW
    assert stored(path).watermark_query != stored(path).query
    calls = []
    def success(request):
        calls.append(request)
        return httpx.Response(200, json={"articles": []})
    ingest(path, success, NOW + timedelta(hours=3))
    assert calls[0].url.params["startdatetime"] == "20260929150000"


def test_news_channel_excludes_signals_and_known_official_bulletin_discovery(tmp_path):
    path = tmp_path / "news.json"
    data = payload()
    data["articles"].append({**data["articles"][0], "url": "https://www.gdacs.org/report.aspx?eventtype=FL&eventid=123"})
    ingest(path, lambda request: httpx.Response(200, json=data))
    news = read_sources(path, now=NOW)
    assert news.channel == "news" and len(news.events) == 1
    assert {source.source_id for source in news.sources} == {"globalvoices", "gdelt", "wikipedia"}
    signals = read_sources(path, now=NOW, channel="signals")
    assert signals.events == [] and {source.source_id for source in signals.sources} == {"gdacs", "nasa"}


def test_cross_provider_canonical_article_keeps_publisher_metadata_and_both_observations(tmp_path):
    from app.news.service import ingest_sources
    path = tmp_path / "news.json"
    gv = (b'<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>Publisher headline</title>'
          b'<link>https://globalvoices.org/story/?id=1</link><pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate>'
          b'<dc:creator>Full Author Credit</dc:creator></item></channel></rss>')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=gv))) as client:
            await ingest_sources(path, source="globalvoices", now=NOW, client=client)
    asyncio.run(run())
    data = payload()
    data["articles"][0]["url"] = "https://globalvoices.org/story/?id=1&utm_source=gdelt"
    ingest(path, lambda request: httpx.Response(200, json=data))
    result = read_sources(path, now=NOW)
    assert len(result.events) == 1 and len(result.events[0].articles) == 1
    article = result.events[0].articles[0]
    assert article.author == "Full Author Credit" and article.published_at == NOW - timedelta(hours=2)
    assert article.license_url == "https://creativecommons.org/licenses/by/3.0/"
    assert {observation.provider_id for observation in article.observations} == {"gdelt", "globalvoices"}
    assert result.duplicates_excluded == 1


def test_ingestion_persists_candidate_identity_and_revision_across_membership_growth(tmp_path):
    path = tmp_path / "news.json"
    def records(count):
        return {"articles": [{"url": f"https://publisher-{index}.example/story", "seendate": "20260930T100000Z",
                              "language": "English", "title": "Explosion at Orion chemical plant in Tehran"}
                             for index in range(count)]}
    first = ingest(path, lambda request: httpx.Response(200, json=records(2)))
    assert len(first.events) == 1 and first.events[0].grouping_status == "candidate"
    assert len(first.events[0].articles) == 2
    changed = ingest(path, lambda request: httpx.Response(200, json=records(3)), NOW + timedelta(minutes=15))
    assert len(changed.events) == 1 and len(changed.events[0].articles) == 3
    assert changed.events[0].id == first.events[0].id
    assert changed.events[0].assignment_revision != first.events[0].assignment_revision
    reread = read_sources(path, now=NOW + timedelta(minutes=16))
    assert reread.events[0].id == first.events[0].id
    assert reread.events[0].assignment_revision == changed.events[0].assignment_revision
    assert len({article.id for article in reread.events[0].articles}) == 3
