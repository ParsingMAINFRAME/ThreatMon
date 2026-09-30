import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.news.polling import NewsLockError, news_lock, poll_delay, poll_news
from app.news.service import read_sources

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def test_cache_lock_excludes_import_and_poller_and_releases_on_failure(tmp_path, monkeypatch, capsys):
    from app import cli
    from app.news import service, polling
    path = tmp_path / "news.json"
    async def forbidden(*args, **kwargs):
        pytest.fail("a second command must not start ingestion or polling")
    monkeypatch.setattr(service, "ingest_sources", forbidden)
    monkeypatch.setattr(polling, "poll_news", forbidden)
    with pytest.raises(RuntimeError, match="operator failure"):
        with news_lock(path):
            with pytest.raises(NewsLockError):
                with news_lock(path):
                    pytest.fail("lock should exclude another owner")
            for command in ["ingest", "poll"]:
                assert cli.main(["news", command, "--source", "gdelt", "--cache-path", str(path)]) == 1
            raise RuntimeError("operator failure")
    assert not path.with_name("news.json.lock").exists()
    with news_lock(path):
        pass
    assert "holds this cache lock" in capsys.readouterr().out


def test_polling_is_single_queue_gdelt_only_and_stops_gracefully(tmp_path, monkeypatch):
    from app.news import polling
    calls = []
    async def run():
        stop = asyncio.Event()
        async def importer(path, *, source):
            calls.append(source)
            stop.set()
            return read_sources(path, now=NOW)
        monkeypatch.setattr(polling, "ingest_sources", importer)
        await poll_news(tmp_path / "news.json", interval_seconds=900, stop_event=stop)
    asyncio.run(run())
    assert calls == ["gdelt"]


def test_poll_delay_respects_provider_backoff_and_interval(tmp_path):
    response = read_sources(tmp_path / "news.json", now=NOW)
    gdelt = next(source for source in response.sources if source.source_id == "gdelt")
    gdelt.next_fetch_at = NOW + timedelta(hours=2)
    assert poll_delay(response, 900, NOW) == 7200
    gdelt.next_fetch_at = NOW - timedelta(minutes=1)
    assert poll_delay(response, 900, NOW) == 900


@pytest.mark.parametrize("interval", [0, 899, 86401])
def test_unsupported_poll_interval_rejected_without_starting_worker(tmp_path, interval):
    with pytest.raises(ValueError):
        asyncio.run(poll_news(tmp_path / "news.json", interval_seconds=interval))
