from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.sources.models import SourceType
from app.domain.threats.models import MapLocation, ThreatCategory


class RawSignal(BaseModel):
    id: str
    title: str
    source_name: str
    source_type: SourceType
    category: ThreatCategory
    citation: str
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    updated_at: datetime | None = None
    connector: str | None = None
    external_id: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    provenance: dict[str, object] = Field(default_factory=dict)
    geography: list[str] = Field(default_factory=list)
    map_location: MapLocation | None = None
    claims: list[str] = Field(default_factory=list)
    is_official: bool = False
    is_demo: bool = True


class Connector(ABC):
    name: str
    feed_url: str
    description: str

    @abstractmethod
    async def fetch(self) -> list[RawSignal]:
        """Fetch raw source records."""

    def parse(self, payload: dict, *, retrieved_at: datetime, is_demo: bool = False) -> list[RawSignal]:
        """Validate a feed payload without network access (implemented by supported connectors)."""
        raise NotImplementedError
