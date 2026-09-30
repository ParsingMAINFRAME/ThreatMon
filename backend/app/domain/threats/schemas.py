from typing import Literal

from pydantic import BaseModel, Field

from app.domain.threats.models import MapLocation, ThreatCategory, ThreatEvent, ThreatScore
from app.domain.threats.status import ThreatStatus


class ThreatCard(BaseModel):
    id: str
    title: str
    category: ThreatCategory
    geography: list[str]
    map_location: MapLocation | None = None
    status: ThreatStatus
    summary: str
    score: ThreatScore
    updated_at: str
    is_demo: bool
    source_count: int


class ThreatListResponse(BaseModel):
    demo_data: bool
    items: list[ThreatCard]
    data_mode: Literal["empty", "demo", "live", "mixed"]
    total: int
    limit: int
    offset: int
    snapshot_id: str | None = Field(
        default=None,
        description=("SHA-256 of all matching ordered card contents before pagination. "
                     "Unchanged filters and sort return the same value across offsets and limits. "
                     "Compare it across pages and restart collection if it changes; this is a "
                     "content fingerprint, not a retained snapshot or pagination cursor."),
    )


class ThreatDetailResponse(BaseModel):
    demo_data: bool
    item: ThreatEvent
    data_mode: Literal["demo", "live"]
