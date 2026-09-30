import asyncio
from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from app.connectors.cisa_kev import CisaKevConnector
from app.connectors.http import FeedError, fetch_json
from app.connectors.usgs_earthquakes import UsgsEarthquakesConnector
from app.domain.ingestion.normalizer import normalize_raw_signal
from app.domain.ingestion.service import threat_from_signal


NOW = datetime(2026, 4, 26, 12, 30, tzinfo=UTC)


def test_usgs_normalizes_reported_facts_and_provenance(feed_fixture):
    raw, = UsgsEarthquakesConnector().parse(feed_fixture("usgs_earthquakes"), retrieved_at=NOW)
    assert raw.external_id == "demoqa001" and raw.is_demo is False
    assert raw.details == {"magnitude": 6.2, "review_status": "automatic"}
    assert raw.published_at.tzinfo == UTC
    source = normalize_raw_signal(raw).source
    assert source.retrieved_at == NOW
    assert source.provenance["feed_url"].startswith("https://earthquake.usgs.gov/")
    assert len(source.provenance["content_sha256"]) == 64
    threat = threat_from_signal(raw)
    assert threat.score.severity == 62
    assert threat.score.priority == 3.56
    assert threat.score.confidence == "low"
    assert any("preliminary" in text for text in threat.key_uncertainties)
    assert any("unmeasured" in text for text in threat.score.rationale)


def test_cisa_has_explicit_unknown_inputs_and_no_unsourced_exposure(feed_fixture):
    payload = feed_fixture("cisa_kev")
    payload["vulnerabilities"][0]["notes"] = "Untrusted additional prose must not enter the dashboard"
    raw, = CisaKevConnector().parse(payload, retrieved_at=NOW)
    threat = threat_from_signal(raw)
    assert raw.external_id == "CVE-2099-0001"
    assert raw.provenance["catalog_version"] == "2026.04.26"
    assert threat.geography == ["Geography not specified by the catalog"]
    assert threat.score.severity == 50 and threat.score.priority == 2.88
    assert threat.score.confidence == "low"
    assert "untrusted" not in threat.model_dump_json().lower()


def test_fixture_signal_stays_demo_and_separate_from_live(feed_fixture):
    connector = UsgsEarthquakesConnector()
    demo, = connector.parse(feed_fixture("usgs_earthquakes"), retrieved_at=NOW, is_demo=True)
    live, = connector.parse(feed_fixture("usgs_earthquakes"), retrieved_at=NOW)
    assert demo.id.startswith("demo-") and demo.id != live.id
    assert demo.title.startswith("[DEMO]")
    assert demo.provenance["input_mode"] == "fixture"


def test_missing_usgs_magnitude_is_not_invented(feed_fixture):
    payload = feed_fixture("usgs_earthquakes")
    payload["features"][0]["properties"]["mag"] = None
    raw, = UsgsEarthquakesConnector().parse(payload, retrieved_at=NOW)
    threat = threat_from_signal(raw)
    assert "Magnitude pending" in threat.title
    assert threat.score.severity == 50
    assert any("Magnitude was not supplied" in text for text in threat.key_uncertainties)


@pytest.mark.parametrize("field,value", [("mag", float("nan")), ("time", "yesterday"), ("url", "javascript:alert(1)"), ("status", "bogus")])
def test_invalid_usgs_records_fail_whole_feed(feed_fixture, field, value):
    payload = feed_fixture("usgs_earthquakes")
    payload["features"][0]["properties"][field] = value
    with pytest.raises(FeedError):
        UsgsEarthquakesConnector().parse(payload, retrieved_at=NOW)


def test_duplicate_and_invalid_cisa_entries_rejected(feed_fixture):
    payload = feed_fixture("cisa_kev")
    payload["vulnerabilities"].append(deepcopy(payload["vulnerabilities"][0]))
    with pytest.raises(FeedError, match="duplicate"):
        CisaKevConnector().parse(payload, retrieved_at=NOW)
    payload = feed_fixture("cisa_kev")
    payload["vulnerabilities"][0]["dateAdded"] = "not-a-date"
    with pytest.raises(FeedError):
        CisaKevConnector().parse(payload, retrieved_at=NOW)


def test_fetch_uses_fixed_endpoint_and_read_only_get(feed_fixture):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=feed_fixture("usgs_earthquakes"))
    async def fetch():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await UsgsEarthquakesConnector(client).fetch()
    signals = asyncio.run(fetch())
    assert len(signals) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == UsgsEarthquakesConnector.feed_url


def test_fetch_retries_transient_failures_and_rejects_invalid_json():
    attempts = 0
    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(503) if attempts == 1 else httpx.Response(200, json={"features": []})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_json(UsgsEarthquakesConnector.feed_url, client)
    assert asyncio.run(run()) == {"features": []}
    assert attempts == 2
    async def invalid():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="not json"))) as client:
            await fetch_json(UsgsEarthquakesConnector.feed_url, client)
    with pytest.raises(FeedError, match="valid JSON"):
        asyncio.run(invalid())
