from fastapi.testclient import TestClient
import pytest

from sqlalchemy.orm import Session

from app.main import app, settings
from app.db.seed import seed_demo_data
from app.db.session import get_db


@pytest.fixture()
def client(db_engine, monkeypatch):
    monkeypatch.setattr(settings, "create_db_on_startup", False)
    with Session(db_engine) as session:
        seed_demo_data(session)
    def isolated_db():
        with Session(db_engine) as session:
            yield session
    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_threat_list_returns_four_demo_items(client: TestClient) -> None:
    response = client.get("/threats")
    data = response.json()

    assert response.status_code == 200
    assert data["demo_data"] is True
    assert len(data["items"]) == 4
    assert all(item["is_demo"] for item in data["items"])
    assert data["data_mode"] == "demo"
    assert data["total"] == 4
    assert all(item["source_count"] >= 1 for item in data["items"])


def test_threat_detail_returns_sources_and_timeline(client: TestClient) -> None:
    response = client.get("/threats/demo-exploited-cyber-vulnerability")
    data = response.json()

    assert response.status_code == 200
    assert data["item"]["category"] == "cybersecurity"
    assert data["item"]["sources"]
    assert data["item"]["timeline"]
    assert "exploit instructions" in data["item"]["sources"][0]["notes"].lower()


def test_map_contract_in_list_and_detail_keeps_null_and_synthetic_points(client):
    items = client.get("/threats").json()["items"]
    assert all("map_location" in item for item in items)
    mapped = [item for item in items if item["map_location"] is not None]
    assert len(mapped) == 2
    assert all(item["map_location"]["origin"] == "synthetic_demo" for item in mapped)
    for item in mapped:
        detail = client.get(f"/threats/{item['id']}").json()["item"]
        assert detail["map_location"] == item["map_location"]
        assert detail["map_location"]["source_id"] in {source["id"] for source in detail["sources"]}
    assert next(item for item in items if item["category"] == "cybersecurity")["map_location"] is None


def test_unknown_threat_returns_404(client: TestClient) -> None:
    response = client.get("/threats/not-a-threat")

    assert response.status_code == 404


def test_sources_endpoint_returns_demo_sources(client: TestClient) -> None:
    response = client.get("/sources")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 5
    assert all(source["is_demo"] for source in data)


def test_filtering_pagination_and_stable_order(client: TestClient):
    data = client.get("/threats", params={"category": "cybersecurity", "q": "edge", "limit": 1}).json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "demo-exploited-cyber-vulnerability"
    all_ids = [item["id"] for item in client.get("/threats").json()["items"]]
    second = client.get("/threats", params={"offset": 1, "limit": 1}).json()
    assert second["total"] == 4
    assert second["items"][0]["id"] == all_ids[1]
    assert second["offset"] == 1 and second["limit"] == 1
    # Mode describes all matched items, even when the page is beyond the end.
    end = client.get("/threats", params={"offset": 999}).json()
    assert end["items"] == [] and end["data_mode"] == "demo"


@pytest.mark.parametrize("params", [{"category": "bogus"}, {"status": "bogus"}, {"data_mode": "mixed"}, {"limit": 101}, {"offset": -1}, {"min_priority": -1}, {"sort": "bogus"}])
def test_invalid_filters_return_validation_error(client, params):
    assert client.get("/threats", params=params).status_code == 422


def test_no_results_are_explicitly_empty(client):
    data = client.get("/threats", params={"q": "nothingmatches"}).json()
    assert data["items"] == [] and data["total"] == 0
    assert data["data_mode"] == "empty" and data["demo_data"] is False
    assert client.get("/threats", params={"q": "%"}).json()["total"] == 0


def test_demo_health_absence_is_uncertainty_not_contradiction(client):
    item = client.get("/threats/demo-unconfirmed-public-health-signal").json()["item"]
    assert item["contradictory_evidence"] == []
    assert all(not claim["contradicts_claim_ids"] for claim in item["extracted_claims"])


def test_connectors_are_read_only_and_truthful_before_fetch(client):
    data = client.get("/ingest/connectors").json()
    assert data["live_ingestion_enabled"] is True
    assert data["automatic_refresh_enabled"] is False
    assert {connector["name"] for connector in data["connectors"]} == {"cisa_kev", "usgs_earthquakes"}
    assert all(connector["state"] == "never_run" for connector in data["connectors"])
    assert client.post("/ingest/connectors").status_code == 405


def test_mixed_and_live_results_are_labeled_per_matched_set(client, db_engine, feed_fixture):
    from datetime import UTC, datetime
    from app.connectors.cisa_kev import CisaKevConnector
    from app.domain.ingestion.service import persist_signals

    raw = CisaKevConnector().parse(feed_fixture("cisa_kev"), retrieved_at=datetime(2026, 4, 26, tzinfo=UTC))
    with Session(db_engine) as session:
        persist_signals(session, raw)
        session.commit()
    mixed = client.get("/threats", params={"limit": 1}).json()
    assert mixed["total"] == 5 and mixed["data_mode"] == "mixed" and mixed["demo_data"] is False
    live = client.get("/threats", params={"data_mode": "live"}).json()
    assert live["total"] == 1 and live["data_mode"] == "live"
    assert live["items"][0]["is_demo"] is False
    detail = client.get(f"/threats/{live['items'][0]['id']}").json()
    assert detail["data_mode"] == "live" and detail["demo_data"] is False
    assert detail["item"]["sources"][0]["provenance"]["connector"] == "cisa_kev"


def test_failed_refresh_exposes_previous_success_and_fixture_does_not_fake_live(client, db_engine, feed_fixture):
    import asyncio
    import httpx
    from app.connectors.cisa_kev import CisaKevConnector
    from app.domain.ingestion.service import ingest_connector

    with Session(db_engine, expire_on_commit=False) as session:
        asyncio.run(ingest_connector(session, CisaKevConnector(), fixture=feed_fixture("cisa_kev")))
    cisa = next(item for item in client.get("/ingest/connectors").json()["connectors"] if item["name"] == "cisa_kev")
    assert cisa["state"] == "never_run" and cisa["last_success_at"] is None
    async def fetch(status):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=feed_fixture("cisa_kev")))) as mock:
            with Session(db_engine, expire_on_commit=False) as session:
                return await ingest_connector(session, CisaKevConnector(mock))
    assert asyncio.run(fetch(200)).success
    assert not asyncio.run(fetch(403)).success
    cisa = next(item for item in client.get("/ingest/connectors").json()["connectors"] if item["name"] == "cisa_kev")
    assert cisa["state"] == "error" and cisa["last_success_at"] is not None
    assert cisa["item_count"] == 1 and "HTTPStatusError" in cisa["error"]
    assert client.get("/threats", params={"data_mode": "live"}).json()["total"] == 1


def test_snapshot_fingerprints_all_matching_cards_before_pagination(client):
    import hashlib
    import json

    full = client.get("/threats").json()
    content = json.dumps(full["items"], sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    assert full["snapshot_id"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert client.get("/threats").json()["snapshot_id"] == full["snapshot_id"]
    for params in [{"limit": 1}, {"limit": 2, "offset": 2}, {"offset": 999}]:
        page = client.get("/threats", params=params).json()
        assert page["snapshot_id"] == full["snapshot_id"]
        assert page["total"] == full["total"]
        offset = params.get("offset", 0)
        limit = params.get("limit", 50)
        assert page["items"] == full["items"][offset:offset + limit]


def test_filtered_snapshot_ignores_nonmatching_updates_and_is_offset_independent(client, db_engine):
    from sqlalchemy import select
    from app.db.models import ThreatEventRecord

    params = {"category": "cybersecurity", "q": "edge", "data_mode": "demo", "sort": "updated"}
    before = client.get("/threats", params=params).json()
    all_before = client.get("/threats").json()
    assert before["total"] == 1
    with Session(db_engine) as session:
        quake = session.scalar(select(ThreatEventRecord).where(ThreatEventRecord.category == "natural_hazard"))
        quake.title = "Revised illustrative quake title"
        session.commit()
    after = client.get("/threats", params={**params, "limit": 1, "offset": 1}).json()
    assert after["items"] == []
    assert after["snapshot_id"] == before["snapshot_id"]
    assert after["data_mode"] == "demo" and after["total"] == 1
    all_after = client.get("/threats").json()
    assert all_after["total"] == all_before["total"]
    assert all_after["snapshot_id"] != all_before["snapshot_id"]


def test_snapshot_changes_for_ingestion_revision_without_count_change(client, db_engine, feed_fixture):
    from datetime import UTC, datetime, timedelta
    from app.connectors.usgs_earthquakes import UsgsEarthquakesConnector
    from app.domain.ingestion.service import persist_signals

    connector = UsgsEarthquakesConnector()
    payload = feed_fixture("usgs_earthquakes")
    now = datetime(2026, 4, 26, 12, 30, tzinfo=UTC)
    demo_only = client.get("/threats", params={"limit": 1}).json()
    with Session(db_engine) as session:
        persist_signals(session, connector.parse(payload, retrieved_at=now))
        session.commit()
    first = client.get("/threats", params={"limit": 1}).json()
    assert first["total"] == demo_only["total"] + 1
    assert first["snapshot_id"] != demo_only["snapshot_id"]
    with Session(db_engine) as session:
        persist_signals(session, connector.parse(payload, retrieved_at=now + timedelta(minutes=1)))
        session.commit()
    unchanged = client.get("/threats", params={"limit": 1, "offset": 1}).json()
    assert unchanged["snapshot_id"] == first["snapshot_id"]
    payload["features"][0]["geometry"]["coordinates"] = [-121, 36, 10]
    payload["features"][0]["properties"]["updated"] += 120000
    with Session(db_engine) as session:
        persist_signals(session, connector.parse(payload, retrieved_at=now + timedelta(minutes=2)))
        session.commit()
    revised = client.get("/threats", params={"limit": 1, "offset": 1}).json()
    assert revised["total"] == first["total"]
    assert revised["snapshot_id"] != first["snapshot_id"]
    # The revised live event lies beyond these demo-leading pages, but must still
    # change their fingerprint so a client cannot silently combine two collections.
    assert revised["items"] == unchanged["items"]


def test_empty_snapshot_is_stable_and_openapi_explains_optional_field(client):
    import hashlib

    first = client.get("/threats", params={"q": "nothingmatches"}).json()
    second = client.get("/threats", params={"q": "nothingmatches", "offset": 999, "limit": 1}).json()
    assert first["snapshot_id"] == second["snapshot_id"] == hashlib.sha256(b"[]").hexdigest()
    schema = client.get("/openapi.json").json()["components"]["schemas"]["ThreatListResponse"]
    assert "snapshot_id" not in schema["required"]
    assert "before pagination" in schema["properties"]["snapshot_id"]["description"]
