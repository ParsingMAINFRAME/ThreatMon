import asyncio
from datetime import timedelta

import httpx
from sqlalchemy import func, select

from app.connectors.cisa_kev import CisaKevConnector
from app.connectors.usgs_earthquakes import UsgsEarthquakesConnector
from app.db.models import IngestionRunRecord, SourceItemRecord, ThreatEventRecord
from app.db.repository import get_threat_event, list_threat_events
from app.domain.ingestion.service import ingest_connector, persist_signals
from tests.test_connectors import NOW


def test_repeat_usgs_ingest_is_idempotent_and_revisions_keep_history(db_session, feed_fixture):
    connector = UsgsEarthquakesConnector()
    payload = feed_fixture("usgs_earthquakes")
    raw, = connector.parse(payload, retrieved_at=NOW)
    counts = persist_signals(db_session, [raw])
    db_session.commit()
    assert counts.inserted == 1
    repeated, = connector.parse(payload, retrieved_at=NOW + timedelta(minutes=1))
    assert persist_signals(db_session, [repeated]).unchanged == 1
    db_session.commit()
    threat = list_threat_events(db_session)[0]
    assert threat.updated_at.tzinfo is not None
    assert len(threat.timeline) == 1 and len(threat.sources) == 1
    assert threat.sources[0].retrieved_at == NOW + timedelta(minutes=1)
    assert threat.sources[0].provenance["first_retrieved_at"] == NOW.isoformat()
    payload["features"][0]["properties"]["mag"] = 6.4
    payload["features"][0]["properties"]["updated"] += 120000
    changed, = connector.parse(payload, retrieved_at=NOW + timedelta(minutes=2))
    assert persist_signals(db_session, [changed]).updated == 1
    db_session.commit()
    revised = get_threat_event(db_session, threat.id)
    assert revised.score.severity == 64
    assert len(revised.timeline) == 2 and len(revised.sources) == 2
    assert {claim.source_id for claim in revised.extracted_claims} == {changed.id}
    assert db_session.scalar(select(func.count()).select_from(ThreatEventRecord)) == 1
    # A stale older USGS snapshot cannot undo a newer revision.
    assert persist_signals(db_session, [raw]).unchanged == 1
    db_session.commit()
    assert get_threat_event(db_session, threat.id).score.severity == 64


def test_timestamp_only_usgs_updates_are_not_material_revisions(db_session, feed_fixture):
    connector = UsgsEarthquakesConnector()
    payload = feed_fixture("usgs_earthquakes")
    raw, = connector.parse(payload, retrieved_at=NOW)
    persist_signals(db_session, [raw])
    db_session.commit()
    payload["features"][0]["properties"]["updated"] += 60000
    latest, = connector.parse(payload, retrieved_at=NOW + timedelta(minutes=1))
    assert latest.id == raw.id
    assert persist_signals(db_session, [latest]).unchanged == 1
    db_session.commit()
    threat = list_threat_events(db_session)[0]
    assert len(threat.sources) == len(threat.timeline) == 1
    assert threat.updated_at == latest.updated_at
    assert threat.sources[0].provenance["event_updated_at"] == latest.updated_at.isoformat()


def test_catalog_revision_can_revert_to_earlier_content(db_session, feed_fixture):
    connector = CisaKevConnector()
    payload = feed_fixture("cisa_kev")
    first, = connector.parse(payload, retrieved_at=NOW)
    persist_signals(db_session, [first])
    db_session.commit()
    payload["vulnerabilities"][0]["product"] = "Changed Appliance"
    second, = connector.parse(payload, retrieved_at=NOW + timedelta(minutes=1))
    assert persist_signals(db_session, [second]).updated == 1
    db_session.commit()
    reverted, = connector.parse(feed_fixture("cisa_kev"), retrieved_at=NOW + timedelta(minutes=2))
    assert persist_signals(db_session, [reverted]).updated == 1
    db_session.commit()
    threat = list_threat_events(db_session)[0]
    assert "Changed Appliance" not in threat.summary
    assert len(threat.timeline) == 3 and len(threat.sources) == 3
    assert len({entry.id for entry in threat.timeline}) == 3
    assert {claim.source_id for claim in threat.extracted_claims} == {threat.timeline[-1].source_ids[0]}
    assert persist_signals(db_session, [reverted]).unchanged == 1
    db_session.commit()
    assert len(list_threat_events(db_session)[0].timeline) == 3


def test_catalog_version_only_change_refreshes_metadata(db_session, feed_fixture):
    connector = CisaKevConnector()
    payload = feed_fixture("cisa_kev")
    first, = connector.parse(payload, retrieved_at=NOW)
    persist_signals(db_session, [first])
    db_session.commit()
    payload["catalogVersion"] = "2026.04.27"
    same, = connector.parse(payload, retrieved_at=NOW + timedelta(days=1))
    assert same.id == first.id
    assert persist_signals(db_session, [same]).unchanged == 1
    db_session.commit()
    threat = list_threat_events(db_session)[0]
    assert len(threat.timeline) == 1
    assert threat.sources[0].provenance["catalog_version"] == "2026.04.27"


def test_failed_ingestion_preserves_previous_snapshot_and_logs_error(db_session, feed_fixture):
    connector = CisaKevConnector()
    success = asyncio.run(ingest_connector(db_session, connector, fixture=feed_fixture("cisa_kev")))
    assert success.success and success.data_mode == "demo"
    bad_payload = feed_fixture("cisa_kev")
    bad_payload["vulnerabilities"].append({"cveID": "invalid"})
    failed = asyncio.run(ingest_connector(db_session, connector, fixture=bad_payload))
    assert not failed.success and failed.error == "Invalid CVE ID"
    assert db_session.scalar(select(func.count()).select_from(ThreatEventRecord)) == 1
    assert db_session.scalar(select(func.count()).select_from(SourceItemRecord)) == 1
    assert db_session.scalar(select(func.count()).select_from(IngestionRunRecord)) == 2


def test_empty_valid_feed_success_does_not_delete_retained_snapshots(db_session, feed_fixture):
    connector = CisaKevConnector()
    asyncio.run(ingest_connector(db_session, connector, fixture=feed_fixture("cisa_kev")))
    empty = feed_fixture("cisa_kev")
    empty["vulnerabilities"] = []
    result = asyncio.run(ingest_connector(db_session, connector, fixture=empty))
    assert result.success and result.item_count == 0
    assert len(list_threat_events(db_session)) == 1


def test_transport_failure_records_error_without_creating_live_data(db_session):
    async def ingest():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(403))) as client:
            return await ingest_connector(db_session, CisaKevConnector(client))
    result = asyncio.run(ingest())
    assert result.success is False and result.data_mode == "live"
    assert "HTTPStatusError" in result.error
    assert list_threat_events(db_session) == []
