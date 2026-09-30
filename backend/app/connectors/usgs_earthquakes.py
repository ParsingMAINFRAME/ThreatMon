from datetime import datetime
import re
from urllib.parse import urlsplit

import httpx

from app.connectors.http import FeedError, fetch_json
from app.connectors.validation import ensure_unique, epoch_milliseconds, finish_signal, require_number, require_text
from app.core.time import utc_now
from app.domain.ingestion.base import Connector, RawSignal
from app.domain.sources.models import SourceType
from app.domain.threats.models import MapLocation, ThreatCategory


class UsgsEarthquakesConnector(Connector):
    name = "usgs_earthquakes"
    feed_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    description = "USGS M2.5+ earthquakes from the past day; retained snapshots are not a real-time warning service."

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def fetch(self) -> list[RawSignal]:
        payload = await fetch_json(self.feed_url, self.client)
        return self.parse(payload, retrieved_at=utc_now())

    def parse(self, payload: dict, *, retrieved_at: datetime, is_demo: bool = False) -> list[RawSignal]:
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise FeedError("USGS feed must be a GeoJSON FeatureCollection")
        signals = []
        for feature in payload["features"]:
            if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
                raise FeedError("Invalid USGS feature")
            properties = feature["properties"]
            # The catalog includes quarry blasts; do not call those earthquakes.
            if properties.get("type") != "earthquake":
                continue
            external_id = require_text(feature.get("id"), "USGS event ID", max_length=100)
            if not re.fullmatch(r"[A-Za-z0-9_-]+", external_id):
                raise FeedError("Invalid USGS event ID")
            magnitude = properties.get("mag")
            if magnitude is not None:
                magnitude = require_number(magnitude, "USGS magnitude", minimum=-10, maximum=15)
            place = properties.get("place")
            place = require_text(place, "USGS place") if place else "Location not supplied by USGS"
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict) or geometry.get("type") != "Point":
                raise FeedError("USGS event geometry must be a GeoJSON Point")
            coordinates = geometry.get("coordinates")
            if not isinstance(coordinates, list) or len(coordinates) not in {2, 3}:
                raise FeedError("USGS Point must supply longitude and latitude")
            lon = require_number(coordinates[0], "USGS longitude", minimum=-180, maximum=180)
            lat = require_number(coordinates[1], "USGS latitude", minimum=-90, maximum=90)
            location = MapLocation(
                lon=lon, lat=lat, label=f"Illustrative demo point — {place}"[:500] if is_demo else place,
                precision="illustrative" if is_demo else "reported_point",
                origin="synthetic_demo" if is_demo else "source_reported", source_id=external_id,
            )
            published = epoch_milliseconds(properties.get("time"), "USGS event time")
            updated = epoch_milliseconds(properties.get("updated"), "USGS update time")
            url = require_text(properties.get("url"), "USGS event URL", max_length=2000)
            parsed_url = urlsplit(url)
            if parsed_url.scheme != "https" or parsed_url.netloc != "earthquake.usgs.gov":
                raise FeedError("USGS event URL must use the official HTTPS domain")
            status = properties.get("status")
            if status not in {"automatic", "reviewed"}:
                raise FeedError("Invalid USGS review status")
            mag_text = f"M {magnitude:g}" if magnitude is not None else "Magnitude pending"
            title = f"{mag_text} earthquake — {place}"[:500]
            signals.append(finish_signal(RawSignal(
                id=external_id, connector=self.name, external_id=external_id,
                title=f"[DEMO] {title}"[:500] if is_demo else title,
                source_name="DEMO USGS-shaped fixture" if is_demo else "USGS Earthquake Hazards Program",
                source_type=SourceType.OFFICIAL, category=ThreatCategory.NATURAL_HAZARD,
                citation=f"{'DEMO fixture; ' if is_demo else ''}USGS event {external_id}; {url}",
                url=url, published_at=published, updated_at=updated, retrieved_at=retrieved_at,
                geography=[place], claims=[f"USGS reports an earthquake at {place} on {published.isoformat()}.", f"USGS review status: {status}."] + ([f"Reported magnitude: {magnitude:g}."] if magnitude is not None else []),
                map_location=location,
                details={"magnitude": magnitude, "review_status": status},
                provenance={"feed_url": self.feed_url, "event_updated_at": updated.isoformat(),
                            "location_geometry": {"type": "Point", "coordinates": [lon, lat]},
                            "location_origin": location.origin},
                is_official=True, is_demo=is_demo,
            )))
        return ensure_unique(signals)
