"""GDELT bulk-file contract, exercised with synthetic GKG rows; no real file is imported."""

import asyncio
from datetime import UTC, datetime, timedelta
import io
import zipfile

import httpx
import pytest

from app.core.config import get_settings
from app.news.gdelt_bulk import BULK_QUERY, file_times, file_url, latest_file_time, parse_gkg_file
from app.news.service import NewsError, ingest_gdelt, read_news

NOW = datetime(2026, 10, 4, 21, 50, tzinfo=UTC)
LATEST = datetime(2026, 10, 4, 21, 45, tzinfo=UTC)
LASTUPDATE = (b"28696 9e86 http://data.gdeltproject.org/gdeltv2/20261004214500.export.CSV.zip\n"
              b"54133 2bd0 http://data.gdeltproject.org/gdeltv2/20261004214500.mentions.CSV.zip\n"
              b"2156336 2fce http://data.gdeltproject.org/gdeltv2/20261004214500.gkg.csv.zip\n")


def row(url, title, locations, domain="publisher.example"):
    columns = [""] * 27
    columns[0], columns[1], columns[3], columns[4], columns[9] = "20261004214500-1", "20261004214500", domain, url, locations
    columns[26] = f"<PAGE_AUTHORS>Someone</PAGE_AUTHORS><PAGE_TITLE>{title}</PAGE_TITLE>"
    return "\t".join(columns)


ROWS = [
    row("https://publisher.example/kyiv?utm_source=x", "Russian drones hit plant in Kyiv, Ukraine &amp; kill one", "4#Kyiv, Kyyiv, Misto, Ukraine#UP#UP12#50.4333#30.5167#-1044367"),
    row("https://courier.example/athens", "One dead in alleged Athens shooting", "3#Athens, Alabama, United States#US#USAL#34.8#-86.9#113286"),
    row("https://courier.example/athens-2", "Second alleged Athens shooting", "4#Athens, Attiki, Greece#GR#GR35#37.98#23.73#-814876;3#Limestone County, Alabama, United States#US#USAL#34.8#-86.9#1;2#Alabama, United States#US#USAL#32.8#-86.8#AL"),
    row("https://sport.example/match", "Morocco win cup after late goal", "1#Morocco#MO#MO#32#-5#MO"),
    row("https://nowhere.example/blast", "Explosion reported in Tehran", ""),
    row("ftp://files.example/report", "Bombing in Baghdad", "4#Baghdad, Baghdad, Iraq#IZ#IZ07#33.3#44.4#-3102875"),
    "short\trow",
]


def archive(*rows, name="20261004214500.gkg.csv"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr(name, "\n".join(rows) + "\n")
    return buffer.getvalue()


def test_lastupdate_yields_only_a_file_time_and_urls_are_built_locally():
    assert latest_file_time(LASTUPDATE) == LATEST
    assert file_url(LATEST) == "https://data.gdeltproject.org/gdeltv2/20261004214500.gkg.csv.zip"
    for body in (b"", b"1 2 http://evil.example/gdeltv2/x.gkg.csv.zip\n", b"1 2 http://data.gdeltproject.org/gdeltv2/99999999999999.gkg.csv.zip\n"):
        with pytest.raises(NewsError):
            latest_file_time(body)


def test_unread_files_are_bounded_to_four_per_import_and_report_skips():
    assert file_times(LATEST, None) == ([LATEST - timedelta(minutes=15 * step) for step in (3, 2, 1, 0)], False)
    assert file_times(LATEST, LATEST) == ([], False)
    assert file_times(LATEST, LATEST - timedelta(minutes=30)) == ([LATEST - timedelta(minutes=15), LATEST], False)
    times, skipped = file_times(LATEST, LATEST - timedelta(hours=3))
    assert len(times) == 4 and times[-1] == LATEST and skipped


def test_only_placeable_headlines_confirmed_by_gdelt_locations_are_kept():
    articles = parse_gkg_file(archive(*ROWS), file_time=LATEST, retrieved_at=NOW)
    assert [article.canonical_url for article in articles] == ["https://publisher.example/kyiv"]
    article = articles[0]
    assert article.headline == "Russian drones hit plant in Kyiv, Ukraine & kill one"
    assert article.publisher == article.publisher_id == "publisher.example" and article.source_id == "gdelt"
    assert article.published_at is None and article.first_seen_at == NOW
    observation = article.observations[0]
    assert observation.provider_timestamp == LATEST and observation.provider_url == file_url(LATEST)
    assert "Someone" not in article.model_dump_json()


@pytest.mark.parametrize("body", [b"not a zip", archive("a", name="one.csv")[:40]], ids=["not-zip", "truncated"])
def test_unreadable_archives_fail_the_source(body):
    with pytest.raises(NewsError):
        parse_gkg_file(body, file_time=LATEST, retrieved_at=NOW)


def test_archive_with_several_members_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        target.writestr("a.csv", "x")
        target.writestr("b.csv", "y")
    with pytest.raises(NewsError):
        parse_gkg_file(buffer.getvalue(), file_time=LATEST, retrieved_at=NOW)


def run(path, handler, now=NOW):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ingest_gdelt(path, client=client, now=now)
    return asyncio.run(go())


def test_bulk_import_places_headlines_tracks_progress_and_never_calls_the_search_api(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "news_gdelt_mode", "bulk")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        assert request.url.host == "data.gdeltproject.org" and request.url.scheme == "https"
        if request.url.path.endswith("lastupdate.txt"):
            return httpx.Response(200, content=LASTUPDATE)
        return httpx.Response(200, content=archive(*ROWS) if "214500" in request.url.path else archive())
    result = run(tmp_path / "news.json", handler)
    assert len(calls) == 5 and result.fetch_state == "ok"
    status = result.sources[0]
    assert status.item_count == 1 and status.query == BULK_QUERY and not status.possibly_truncated
    assert status.query_window_end == LATEST and status.query_window_start == LATEST - timedelta(hours=1)
    event = result.events[0]
    assert event.scope == "located" and event.location.label == "Kyiv, Ukraine (place named in headline)"
    # Within the cooldown nothing is requested; afterwards only files newer than the watermark are read.
    run(tmp_path / "news.json", lambda request: pytest.fail("cooldown must be respected"), NOW + timedelta(minutes=14))
    calls.clear()
    later = run(tmp_path / "news.json", lambda request: (calls.append(1), httpx.Response(200, content=LASTUPDATE))[1], NOW + timedelta(minutes=16))
    assert calls == [1] and later.fetch_state == "ok" and len(later.events) == 1


def test_a_missing_window_file_is_skipped_and_marks_coverage_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "news_gdelt_mode", "bulk")

    def handler(request):
        if request.url.path.endswith("lastupdate.txt"):
            return httpx.Response(200, content=LASTUPDATE)
        return httpx.Response(200, content=archive(*ROWS)) if "214500" in request.url.path else httpx.Response(404)
    result = run(tmp_path / "news.json", handler)
    status = result.sources[0]
    assert result.fetch_state == "ok" and status.item_count == 1 and status.possibly_truncated
    missing = run(tmp_path / "other.json", lambda request: httpx.Response(404))
    assert missing.fetch_state == "error" and "HTTP 404" in missing.sources[0].error


def test_bulk_failure_preserves_stored_articles_and_backs_off(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "news_gdelt_mode", "bulk")

    def good(request):
        if request.url.path.endswith("lastupdate.txt"):
            return httpx.Response(200, content=LASTUPDATE)
        return httpx.Response(200, content=archive(*ROWS))
    run(tmp_path / "news.json", good)
    failed = run(tmp_path / "news.json", lambda request: httpx.Response(503, headers={"Retry-After": "3600"}), NOW + timedelta(minutes=16))
    status = failed.sources[0]
    assert failed.fetch_state == "error" and "HTTP 503" in status.error and len(failed.events) == 1
    assert status.next_fetch_at == NOW + timedelta(minutes=76) and status.last_success_at == NOW
    assert len(read_news(tmp_path / "news.json", now=NOW + timedelta(minutes=17), source="gdelt").events) == 1
