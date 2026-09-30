from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.sources.models import ExtractedClaim, SourceItem
from app.domain.threats.status import ThreatStatus


class ThreatCategory(StrEnum):
    CYBERSECURITY = "cybersecurity"
    NATURAL_HAZARD = "natural_hazard"
    PUBLIC_HEALTH = "public_health"
    SPACE_PLANETARY = "space_planetary"
    GEOPOLITICAL_INFRASTRUCTURE = "geopolitical_infrastructure"
    AI_RISK = "ai_risk"


class ConfidenceLabel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MapLocation(BaseModel):
    """A cited event point or an explicitly illustrative demo marker, never an impact radius."""

    lon: float = Field(ge=-180, le=180, strict=True, allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90, strict=True, allow_inf_nan=False)
    label: str = Field(min_length=1, max_length=500)
    precision: Literal["reported_point", "illustrative"]
    origin: Literal["source_reported", "synthetic_demo"]
    source_id: str = Field(min_length=1, max_length=160)

    @field_validator("label", "source_id")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def validate_precision(self) -> "MapLocation":
        expected = "illustrative" if self.origin == "synthetic_demo" else "reported_point"
        if self.precision != expected:
            raise ValueError("map precision must match its origin")
        return self


class ThreatScore(BaseModel):
    severity: float = Field(ge=0, le=100)
    credibility: float = Field(ge=0, le=100)
    velocity: float = Field(ge=0, le=100)
    exposure: float = Field(ge=0, le=100)
    uncertainty_penalty: float = Field(ge=0, le=100)
    priority: float = Field(ge=0, le=100)
    confidence: ConfidenceLabel
    rationale: list[str] = Field(default_factory=list)


class ThreatTimelineEntry(BaseModel):
    id: str
    occurred_at: datetime
    title: str
    description: str
    source_ids: list[str] = Field(default_factory=list)
    material_change: bool = True

    @field_validator("title", "description")
    @classmethod
    def require_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be empty")
        return cleaned


class ThreatEvent(BaseModel):
    id: str
    title: str
    category: ThreatCategory
    geography: list[str]
    map_location: MapLocation | None = None
    status: ThreatStatus
    summary: str
    score: ThreatScore
    sources: list[SourceItem]
    extracted_claims: list[ExtractedClaim] = Field(default_factory=list)
    timeline: list[ThreatTimelineEntry] = Field(default_factory=list)
    key_uncertainties: list[str] = Field(default_factory=list)
    contradictory_evidence: list[str] = Field(default_factory=list)
    next_watch_items: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    updated_at: datetime
    is_demo: bool = True

    @model_validator(mode="after")
    def validate_map_source(self) -> "ThreatEvent":
        if self.map_location is not None:
            sources = {source.id: source for source in self.sources}
            source = sources.get(self.map_location.source_id)
            if source is None:
                raise ValueError("map location must cite an attached source")
            if self.map_location.origin == "synthetic_demo" and (not self.is_demo or not source.is_demo):
                raise ValueError("illustrative map locations require demo event and source")
            if self.map_location.origin == "source_reported" and (self.is_demo or source.is_demo):
                raise ValueError("demo map locations must be labeled synthetic_demo")
        return self

    @field_validator("title", "summary")
    @classmethod
    def require_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be empty")
        return cleaned
