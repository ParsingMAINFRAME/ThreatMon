import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
from pydantic import ValidationError
import pytest

from app.news.demo import DEMO_AS_OF, demo_news
from app.news.models import NewsArticle, NewsResponse
from app.news.service import NASA_FEED_URL, MAX_FEED_BYTES, ingest_news, parse_nasa_feed, read_news
from app.news.urls import ArticleCandidate, canonical_url, deduplicate_articles


NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def rss(count=1, *, link="https://www.nasa.gov/news/example/?utm_source=rss", date="Wed, 30 Sep 2026 10:00:00 GMT"):
    items = "".join(f"<item><title>NASA report {i}</title><link>{link.replace('&', '&amp;')}&amp;story={i}</link>"
                    f"<pubDate>{date}</pubDate><description>&lt;p&gt;Published update {i}.&lt;/p&gt;</description></item>" for i in range(count))
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>NASA</title>{items}</channel></rss>'.encode()


def article(article_id, url, key=None, publisher="NASA"):
    return NewsArticle(id=article_id, canonical_url=url, headline="Published agency item", publisher=publisher,
                       published_at=NOW - timedelta(hours=1), retrieved_at=NOW, summary="Agency publication.",
                       is_demo=False, syndication_key=key, duplicate_urls=[])


def ingest(path, handler, now=NOW):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ingest_news(path, client=client, now=now)
    return asyncio.run(run())


def test_demo_truth_unique_counts_and_time_windows():
    data = demo_news()
    assert data.edition == "demo" and data.fetch_state == "demo"
    assert data.as_of == DEMO_AS_OF and data.fetched_at is None and data.last_attempt_at is None
    assert len(data.events) == 6 and data.duplicates_excluded >= 3
    iran = next(event for event in data.events if event.id == "demo-iran-explosion")
    low = next(event for event in data.events if event.id == "demo-chile-service-restored")
    assert len(iran.articles) == 35 and iran.status == "unconfirmed" and iran.severity == "high"
    assert len(low.articles) == 5 and low.status == "resolved" and low.severity == "low"
    assert len({item.id for item in iran.articles}) == 35
    assert all(timedelta(0) <= DEMO_AS_OF - item.published_at <= timedelta(hours=24) for item in iran.articles)
    assert len({item.publisher for item in iran.articles}) > 1
    assert any(event.scope == "global" for event in data.events)
    assert any(event.scope == "unlocated" for event in data.events)
    for event in data.events:
        assert event.is_demo and "DEMO" in event.title and "DEMO" in event.summary
        assert "synthetic" in event.severity_basis.lower()
        for item in event.articles:
            assert item.is_demo and item.canonical_url is None and not item.duplicate_urls
            assert "DEMO" in item.headline and "DEMO" in item.summary and item.publisher.startswith("DEMO ")
            assert timedelta(0) <= DEMO_AS_OF - item.published_at <= timedelta(days=7)
        if event.location:
            assert event.location.precision == "illustrative" and "DEMO" in event.location.label


def test_contract_rejects_mixed_demo_truth_and_invalid_coordinates():
    data = demo_news().model_dump(mode="json")
    data["events"][0]["articles"][0]["is_demo"] = False
    with pytest.raises(ValidationError):
        NewsResponse.model_validate(data)
    data = demo_news().model_dump(mode="json")
    data["events"][0]["location"]["lat"] = float("nan")
    with pytest.raises(ValidationError):
        NewsResponse.model_validate(data)
    data = demo_news().model_dump(mode="json")
    data["events"][0]["articles"][0]["canonical_url"] = "https://www.nasa.gov/fake"
    with pytest.raises(ValidationError):
        NewsResponse.model_validate(data)


def test_canonical_urls_drop_tracking_but_keep_semantic_query():
    assert canonical_url("HTTPS://WWW.NASA.GOV:443/story?b=2&utm_source=x&a=1#fragment") == "https://www.nasa.gov/story?a=1&b=2"
    assert canonical_url("https://www.nasa.gov/story?id=1") != canonical_url("https://www.nasa.gov/story?id=2")
    assert canonical_url("https://www.nasa.gov/story?x=1&x=2") != canonical_url("https://www.nasa.gov/story?x=1")


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "//www.nasa.gov/a", "https://user:pass@www.nasa.gov/a", "http://localhost/a", "http://127.0.0.1/a", "http://[::1]/a", "https://www.nasa.gov/a\nInjected: header"])
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_dedup_uses_only_declared_identities_and_is_order_independent():
    records = [ArticleCandidate(article("b", "https://www.nasa.gov/a?utm_source=other", "wire-a")),
               ArticleCandidate(article("a", "https://www.nasa.gov/a", "wire-a")),
               ArticleCandidate(article("c", "https://science.nasa.gov/reprint", "wire-a", "NASA Science")),
               ArticleCandidate(article("d", "https://www.nasa.gov/d"))]
    first, excluded = deduplicate_articles(records)
    reversed_result, reversed_excluded = deduplicate_articles(list(reversed(records)))
    assert excluded == reversed_excluded == 2 and len(first) == 2
    assert [item.model_dump() for item in first] == [item.model_dump() for item in reversed_result]
    assert len({item.headline for item in first}) == 1  # Same headline is not an identity.
    assert any(item.duplicate_urls for item in first)


def test_nasa_items_stay_independent_unlocated_and_have_unknown_severity():
    events, duplicates = parse_nasa_feed(rss(15), retrieved_at=NOW)
    assert len(events) == 10 and duplicates == 0
    for event in events:
        assert event.scope == "unlocated" and event.location is None
        assert event.status == "reported" and event.severity == "unknown" and not event.is_demo
        assert len(event.articles) == 1 and event.articles[0].publisher == "NASA"
        assert event.articles[0].published_at.tzinfo == UTC
        assert "<p>" not in event.articles[0].summary
        assert event.articles[0].summary == "NASA published this article. Consult the original source for its full context."
        assert "Published update" not in event.model_dump_json()


@pytest.mark.parametrize("payload", [b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel>&x;</channel></rss>',
                                    b'<rss><channel><item></rss>', b'<html>Access denied</html>',
                                    rss(date="invalid"), rss(link="https://evil.example/nasa"),
                                    rss(link="javascript:alert(1)"), b'x' * (MAX_FEED_BYTES + 1)],
                         ids=["entity", "malformed", "not-rss", "invalid-date", "foreign-url", "script-url", "oversized"])
def test_unsafe_or_invalid_xml_preserves_validation_boundary(payload):
    with pytest.raises(ValueError):
        parse_nasa_feed(payload, retrieved_at=NOW)


def test_cache_conditional_requests_minimum_interval_and_304(tmp_path):
    cache = tmp_path / "news.json"
    calls = []
    def first(request):
        calls.append(request)
        return httpx.Response(200, content=rss(), headers={"ETag": '"version-1"', "Last-Modified": "Wed, 30 Sep 2026 10:00:00 GMT"})
    assert ingest(cache, first).fetch_state == "ok"
    assert len(calls) == 1 and str(calls[0].url) == NASA_FEED_URL and calls[0].method == "GET"
    assert ingest(cache, first, NOW + timedelta(seconds=299)).fetched_at == NOW
    assert len(calls) == 1
    def unchanged(request):
        calls.append(request)
        assert request.headers["if-none-match"] == '"version-1"'
        assert request.headers["if-modified-since"] == "Wed, 30 Sep 2026 10:00:00 GMT"
        return httpx.Response(304)
    result = ingest(cache, unchanged, NOW + timedelta(minutes=5))
    assert result.fetched_at == NOW + timedelta(minutes=5) and result.fetch_state == "ok"
    assert result.events[0].articles[0].retrieved_at == NOW
    assert read_news(cache, now=NOW + timedelta(minutes=6)).events == result.events


def test_failed_fetch_keeps_good_snapshot_and_records_truthful_attempt(tmp_path):
    cache = tmp_path / "news.json"
    good = ingest(cache, lambda request: httpx.Response(200, content=rss()))
    failed_at = NOW + timedelta(minutes=6)
    result = ingest(cache, lambda request: httpx.Response(403, text="private response body"), failed_at)
    assert result.fetch_state == "error" and result.last_attempt_at == failed_at
    assert result.events == good.events and result.fetched_at == good.fetched_at
    assert "private response" not in result.error
    reread = read_news(cache, now=failed_at)
    assert reread.fetch_state == "error" and reread.events == good.events
    assert ingest(cache, lambda request: pytest.fail("failure cooldown must prevent another request"), failed_at + timedelta(seconds=20)).fetch_state == "error"


def test_first_failure_never_claims_success_and_retries_are_bounded(tmp_path):
    calls = []
    def fail(request):
        calls.append(request)
        return httpx.Response(503)
    result = ingest(tmp_path / "news.json", fail)
    assert len(calls) == 3 and result.fetch_state == "error"
    assert result.fetched_at is None and result.events == []


def test_oversized_stream_rejected_and_redirect_not_followed(tmp_path):
    result = ingest(tmp_path / "large.json", lambda request: httpx.Response(200, content=b"x" * (MAX_FEED_BYTES + 1)))
    assert result.fetch_state == "error" and not result.events
    result = ingest(tmp_path / "redirect.json", lambda request: httpx.Response(302, headers={"Location": "http://127.0.0.1/private"}))
    assert result.fetch_state == "error" and not result.events


def test_read_missing_or_corrupt_snapshot_is_safe_and_read_only(tmp_path):
    cache = tmp_path / "news.json"
    data = read_news(cache, now=NOW)
    assert data.fetch_state == "never_fetched" and not cache.exists() and data.events == []
    cache.write_text("invalid JSON", encoding="utf-8")
    assert read_news(cache, now=NOW).fetch_state == "error"
    assert cache.read_text() == "invalid JSON"


def test_news_api_is_read_only_and_editions_cannot_mix(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.news.routes import router
    monkeypatch.setattr(get_settings(), "news_snapshot_path", str(tmp_path / "absent.json"))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        demo = client.get("/news?edition=demo")
        assert demo.status_code == 200 and demo.json()["fetch_state"] == "demo"
        live = client.get("/news?edition=snapshot")
        assert live.status_code == 200 and live.json()["fetch_state"] == "never_fetched"
        assert live.json()["events"] == []
        assert client.get("/news?edition=mixed").status_code == 422
        assert client.post("/news").status_code == 405


def test_utf16_entity_declaration_and_timezone_free_or_future_dates_rejected():
    xml = '<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel>&x;</channel></rss>'
    for body in [xml.encode("utf-16"), xml.encode("utf-32"), rss(date="Wed, 30 Sep 2026 10:00:00"), rss(date="Thu, 01 Oct 2026 10:00:00 GMT")]:
        with pytest.raises(ValueError):
            parse_nasa_feed(body, retrieved_at=NOW)


def test_retry_after_prevents_early_retries_and_survives_process_boundary(tmp_path):
    cache = tmp_path / "news.json"
    calls = []
    def busy(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "1200"})
    assert ingest(cache, busy).fetch_state == "error" and len(calls) == 1
    assert ingest(cache, lambda request: pytest.fail("must honor server backoff"), NOW + timedelta(minutes=10)).fetch_state == "error"
    assert ingest(cache, lambda request: httpx.Response(200, content=rss()), NOW + timedelta(minutes=20)).fetch_state == "ok"


def test_server_cache_control_and_304_without_cache(tmp_path):
    cache = tmp_path / "news.json"
    assert ingest(cache, lambda request: httpx.Response(200, content=rss(), headers={"Cache-Control": "public, max-age=900"})).fetch_state == "ok"
    assert ingest(cache, lambda request: pytest.fail("must honor longer cache lifetime"), NOW + timedelta(minutes=10)).fetch_state == "ok"
    empty = ingest(tmp_path / "empty.json", lambda request: httpx.Response(304))
    assert empty.fetch_state == "error" and empty.fetched_at is None and not empty.events


def test_failed_atomic_write_does_not_overwrite_good_snapshot(tmp_path, monkeypatch):
    from app.news import service
    cache = tmp_path / "news.json"
    first = ingest(cache, lambda request: httpx.Response(200, content=rss()))
    contents = cache.read_bytes()
    def denied(*args):
        raise PermissionError("private local path must never reach response")
    monkeypatch.setattr(service.os, "replace", denied)
    result = ingest(cache, lambda request: httpx.Response(200, content=rss(2)), NOW + timedelta(minutes=10))
    assert result.fetch_state == "error" and result.events == first.events
    assert cache.read_bytes() == contents and "private local path" not in result.error
    assert not list(tmp_path.glob("news-*.tmp"))


def test_cli_news_ingest_does_not_initialize_or_touch_sql(tmp_path, monkeypatch, capsys):
    from app import cli
    from app.news import service
    async def fake_ingest(path):
        assert path == tmp_path / "selected.json"
        return read_news(path, now=NOW)
    monkeypatch.setattr(service, "ingest_news", fake_ingest)
    monkeypatch.setattr(cli, "init_db", lambda *args, **kwargs: pytest.fail("news must not migrate SQL"))
    monkeypatch.setattr(cli, "make_engine", lambda *args, **kwargs: pytest.fail("news must not connect to SQL"))
    assert cli.main(["news", "ingest", "--cache-path", str(tmp_path / "selected.json")]) == 0
    assert '"edition": "snapshot"' in capsys.readouterr().out
