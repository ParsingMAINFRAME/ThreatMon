from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
import pytest

from app.connectors.cisa_kev import CisaKevConnector
from app.connectors.http import FeedError
from app.connectors.usgs_earthquakes import UsgsEarthquakesConnector
from app.data.demo import seeded_threats
from app.db.repository import get_threat_event, list_threat_events, replace_threats
from app.domain.ingestion.service import persist_signals, threat_from_signal
from app.domain.threats.models import MapLocation, ThreatEvent


NOW = datetime(2026, 4, 26, 12, 30, tzinfo=UTC)


def test_live_usgs_point_is_reported_geometry_with_attached_citation(feed_fixture):
    raw, = UsgsEarthquakesConnector().parse(feed_fixture("usgs_earthquakes"), retrieved_at=NOW)
    threat = threat_from_signal(raw)
    assert threat.map_location.model_dump() == {
        "lon": -120.0, "lat": 35.0, "label": "Synthetic coastal test region",
        "precision": "reported_point", "origin": "source_reported", "source_id": raw.id,
    }
    source, = threat.sources
    assert source.id == threat.map_location.source_id
    assert source.provenance["location_geometry"] == {"type": "Point", "coordinates": [-120.0, 35.0]}
    assert source.provenance["location_origin"] == "source_reported"


@pytest.mark.parametrize("geometry", [
    None, {}, {"type": "Polygon", "coordinates": [[-120, 35]]},
    {"type": "Point", "coordinates": [-120]},
    {"type": "Point", "coordinates": "-120,35"},
    {"type": "Point", "coordinates": [181, 35]},
    {"type": "Point", "coordinates": [-120, 91]},
    {"type": "Point", "coordinates": [float("nan"), 35]},
    {"type": "Point", "coordinates": [-120, float("inf")]},
    {"type": "Point", "coordinates": [True, 35]},
    {"type": "Point", "coordinates": ["-120", 35]},
])
def test_invalid_usgs_geometry_is_rejected_without_guessing(feed_fixture, geometry):
    payload = feed_fixture("usgs_earthquakes")
    payload["features"][0]["geometry"] = geometry
    with pytest.raises(FeedError):
        UsgsEarthquakesConnector().parse(payload, retrieved_at=NOW)


def test_fixture_points_and_seed_points_are_explicitly_illustrative(feed_fixture):
    raw, = UsgsEarthquakesConnector().parse(feed_fixture("usgs_earthquakes"), retrieved_at=NOW, is_demo=True)
    threat = threat_from_signal(raw)
    for event in [threat, *seeded_threats()]:
        if event.map_location is not None:
            assert event.is_demo
            assert event.map_location.origin == "synthetic_demo"
            assert event.map_location.precision == "illustrative"
            assert "illustrative" in event.map_location.label.lower()
            assert event.map_location.source_id in {source.id for source in event.sources}
    assert raw.provenance["location_origin"] == "synthetic_demo"


def test_catalog_and_nonterrestrial_events_have_no_invented_point(feed_fixture):
    raw, = CisaKevConnector().parse(feed_fixture("cisa_kev"), retrieved_at=NOW)
    assert raw.map_location is None and threat_from_signal(raw).map_location is None
    seeds = {threat.id: threat for threat in seeded_threats()}
    cyber = seeds["demo-exploited-cyber-vulnerability"]
    asteroid = next(threat for threat in seeds.values() if threat.category == "space_planetary")
    assert cyber.map_location is None and cyber.geography == ["Global"]
    assert asteroid.map_location is None and "Near-Earth space" in asteroid.geography


@pytest.mark.parametrize("field,value", [
    ("lon", 180.1), ("lat", -90.1), ("lon", float("nan")),
    ("lat", float("inf")), ("lon", "10"), ("lat", True),
    ("label", " "), ("source_id", " "), ("precision", "illustrative"),
])
def test_map_location_schema_rejects_invalid_or_misleading_values(field, value):
    data = {"lon": 10.0, "lat": 20.0, "label": "Agency epicenter", "source_id": "source",
            "precision": "reported_point", "origin": "source_reported"}
    data[field] = value
    with pytest.raises(ValidationError):
        MapLocation.model_validate(data)


def test_threat_point_must_reference_its_evidence_and_respect_demo_state():
    quake = next(threat for threat in seeded_threats() if threat.map_location is not None)
    data = quake.model_dump()
    data["map_location"]["source_id"] = "unattached-source"
    with pytest.raises(ValidationError, match="attached source"):
        ThreatEvent.model_validate(data)
    data = quake.model_dump()
    data["is_demo"] = False
    with pytest.raises(ValidationError, match="demo event"):
        ThreatEvent.model_validate(data)


def test_optional_points_round_trip_in_repository(db_session):
    seeds = seeded_threats()
    replace_threats(db_session, seeds)
    db_session.commit()
    actual = {event.id: event.map_location for event in list_threat_events(db_session)}
    assert actual == {event.id: event.map_location for event in seeds}
    assert sum(location is not None for location in actual.values()) == 2


def test_geometry_revision_changes_marker_and_preserves_source_history(db_session, feed_fixture):
    connector = UsgsEarthquakesConnector()
    payload = feed_fixture("usgs_earthquakes")
    original, = connector.parse(payload, retrieved_at=NOW)
    persist_signals(db_session, [original])
    db_session.commit()
    payload["features"][0]["geometry"]["coordinates"] = [-121, 36, 10]
    payload["features"][0]["properties"]["updated"] += 60000
    revised, = connector.parse(payload, retrieved_at=NOW + timedelta(minutes=1))
    assert revised.id != original.id
    assert persist_signals(db_session, [revised]).updated == 1
    db_session.commit()
    event = get_threat_event(db_session, f"usgs_earthquakes-{original.external_id}")
    assert (event.map_location.lon, event.map_location.lat) == (-121, 36)
    assert event.map_location.source_id == revised.id
    assert len(event.sources) == len(event.timeline) == 2
    old_source = next(source for source in event.sources if source.id == original.id)
    assert old_source.provenance["location_geometry"]["coordinates"] == [-120.0, 35.0]
