from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SourceType(StrEnum):
    OFFICIAL = "official"
    VENDOR = "vendor"
    REPUTABLE_NEWS = "reputable_news"
    PUBLIC_DATASET = "public_dataset"
    LOCAL_REPORT = "local_report"
    SOCIAL_OR_COMMUNITY = "social_or_community"
    UNKNOWN = "unknown"


class SourceReliabilityTier(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ClaimSupportLevel(StrEnum):
    CONFIRMED = "confirmed"
    CORROBORATED = "corroborated"
    SINGLE_SOURCE = "single_source"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


class SourceItem(BaseModel):
    id: str
    title: str
    source_name: str
    source_type: SourceType
    reliability_tier: SourceReliabilityTier = SourceReliabilityTier.UNKNOWN
    citation: str
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    is_official: bool = False
    is_demo: bool = True
    notes: str | None = None
    provenance: dict[str, object] = Field(default_factory=dict)

    @field_validator("title", "source_name", "citation")
    @classmethod
    def require_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be empty")
        return cleaned


class ExtractedClaim(BaseModel):
    id: str
    source_id: str
    text: str
    support_level: ClaimSupportLevel = ClaimSupportLevel.UNKNOWN
    confidence: float = Field(ge=0, le=1)
    is_material: bool = True
    contradicts_claim_ids: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def require_claim_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("claim text must not be empty")
        return cleaned
