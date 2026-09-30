import hashlib
import json
import math
from datetime import UTC, datetime

from app.connectors.http import FeedError
from app.domain.ingestion.base import RawSignal


def require_text(value: object, name: str, *, max_length: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise FeedError(f"Invalid {name}")
    return value.strip()


def require_number(value: object, name: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise FeedError(f"Invalid {name}")
    return float(value)


def epoch_milliseconds(value: object, name: str) -> datetime:
    number = require_number(value, name, minimum=0, maximum=253402300799000)
    try:
        return datetime.fromtimestamp(number / 1000, UTC)
    except (ValueError, OSError, OverflowError) as error:
        raise FeedError(f"Invalid {name}") from error


def finish_signal(raw: RawSignal) -> RawSignal:
    # Feed-wide generation/version and retrieval time are not event revisions.
    content = raw.model_dump(mode="json", include={"title", "category", "geography", "claims", "details", "published_at"})
    if raw.map_location is not None:
        # The point is evidence that may change even when the place text does not.
        # Source IDs depend on this hash, so they cannot be part of the hashed content.
        content["map_location"] = raw.map_location.model_dump(exclude={"source_id"})
    revision = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    prefix = "demo-" if raw.is_demo else ""
    raw.id = f"{prefix}{raw.connector}-{raw.external_id}-{revision[:16]}"
    if raw.map_location is not None:
        raw.map_location.source_id = raw.id
    raw.provenance.update({"connector": raw.connector, "external_id": raw.external_id, "content_sha256": revision,
                           "first_retrieved_at": raw.retrieved_at.isoformat() if raw.retrieved_at else None,
                           "input_mode": "fixture" if raw.is_demo else "live"})
    return raw


def ensure_unique(signals: list[RawSignal]) -> list[RawSignal]:
    ids = [signal.external_id for signal in signals]
    if len(set(ids)) != len(ids):
        raise FeedError("Feed contains duplicate event IDs")
    return signals
