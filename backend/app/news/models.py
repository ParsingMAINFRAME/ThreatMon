from datetime import UTC, datetime
import re
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class NewsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewsLocation(NewsModel):
    lat: float = Field(ge=-90, le=90, strict=True, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, strict=True, allow_inf_nan=False)
    label: str = Field(min_length=1, max_length=300)
    precision: Literal["source_point", "approximate_area", "illustrative"]
    confidence: Literal["high", "medium", "low", "unknown"]
    basis: str = Field(min_length=1, max_length=1000)
    source_url: str | None = None

    @field_validator("source_url")
    @classmethod
    def safe_source_url(cls, value: str | None) -> str | None:
        from app.news.urls import canonical_url
        return canonical_url(value) if value is not None else None


class NewsObservation(NewsModel):
    provider_id: str = Field(min_length=1, max_length=100)
    provider_url: str
    provider_timestamp: AwareDatetime | None = None
    provider_timestamp_raw: str | None = Field(default=None, max_length=100)
    retrieved_at: AwareDatetime
    language: str | None = Field(default=None, max_length=100)
    source_country: str | None = Field(default=None, max_length=100)

    @field_validator("provider_timestamp", "retrieved_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @field_validator("provider_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        from app.news.urls import canonical_url
        return canonical_url(value)


class NewsArticle(NewsModel):
    id: str = Field(min_length=1, max_length=160)
    canonical_url: str | None
    headline: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=200)
    published_at: AwareDatetime | None
    first_seen_at: AwareDatetime | None = None
    observations: list[NewsObservation] = Field(default_factory=list, max_length=32)
    retrieved_at: AwareDatetime
    summary: str = Field(min_length=1, max_length=2000)
    is_demo: bool
    syndication_key: str | None = Field(default=None, max_length=200)
    duplicate_urls: list[str] = Field(default_factory=list, max_length=100)
    source_id: str = Field(default="", max_length=100)
    publisher_id: str = Field(default="", max_length=200)
    record_kind: Literal["article", "official_report"] = "article"
    author: str | None = Field(default=None, max_length=300)
    license_url: str | None = None
    source_window_start: AwareDatetime | None = None
    source_window_end: AwareDatetime | None = None
    # Editor-supplied context from a curated listing (Wikipedia Current events): the portal section,
    # the topic headings the entry sits under, and the article titles the entry links to.
    editor_section: str | None = Field(default=None, max_length=100)
    editor_topics: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=4)
    linked_titles: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=32)

    @field_validator("published_at", "first_seen_at", "retrieved_at", "source_window_start", "source_window_end")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def honest_origin_and_urls(self) -> "NewsArticle":
        from app.news.urls import canonical_url
        if not self.source_id:
            self.source_id = "demo" if self.is_demo else "nasa"
        if not self.publisher_id:
            self.publisher_id = re.sub(r"[^a-z0-9]+", "-", self.publisher.lower()).strip("-")
        if self.first_seen_at is None and not self.is_demo:
            self.first_seen_at = self.retrieved_at
        if self.license_url is not None:
            self.license_url = canonical_url(self.license_url)
        if self.is_demo:
            if self.canonical_url is not None or self.duplicate_urls:
                raise ValueError("Demo articles have no external URLs")
            if not all(value.startswith("DEMO ") for value in (self.headline, self.summary, self.publisher)):
                raise ValueError("Demo articles and fictitious publishers require explicit DEMO labels")
        else:
            if self.canonical_url is None:
                raise ValueError("Published articles require a safe source URL")
            self.canonical_url = canonical_url(self.canonical_url)
            self.duplicate_urls = [canonical_url(url) for url in self.duplicate_urls]
        return self


class NewsEvent(NewsModel):
    id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=100)
    status: Literal["unconfirmed", "developing", "reported", "resolved"]
    severity: Literal["unknown", "low", "moderate", "high"]
    severity_basis: str = Field(min_length=1, max_length=1000)
    grouping_basis: str = Field(min_length=1, max_length=1000)
    location: NewsLocation | None
    scope: Literal["located", "global", "unlocated"]
    is_demo: bool
    articles: list[NewsArticle] = Field(min_length=1, max_length=250)
    source_event_id: str | None = Field(default=None, max_length=160)
    source_alert_level: str | None = Field(default=None, max_length=100)
    grouping_status: Literal["source_event", "single_source", "candidate"] = "source_event"
    grouping_version: str | None = Field(default=None, max_length=100)
    place_hints: list[str] = Field(default_factory=list, max_length=8)
    assignment_revision: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def consistent_evidence(self) -> "NewsEvent":
        if (self.location is not None) != (self.scope == "located"):
            raise ValueError("Only located events may have a map position")
        if any(article.is_demo != self.is_demo for article in self.articles):
            raise ValueError("An event cannot mix synthetic and published articles")
        if len({article.id for article in self.articles}) != len(self.articles):
            raise ValueError("Article identities must be unique within an event")
        if self.is_demo:
            if not self.title.startswith("DEMO ") or not self.summary.startswith("DEMO "):
                raise ValueError("Demo event text requires explicit labels")
            if self.location and (self.location.precision != "illustrative" or not self.location.label.startswith("DEMO ")):
                raise ValueError("Demo map locations must be explicitly illustrative")
        elif self.location and self.location.precision == "illustrative":
            raise ValueError("Published events cannot use synthetic positions")
        return self


class NewsSourceStatus(NewsModel):
    source_id: str = Field(min_length=1, max_length=100)
    publisher_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["news", "official", "discovery"]
    feed_url: str
    terms_url: str
    attribution: str = Field(min_length=1, max_length=1000)
    coverage_note: str = Field(min_length=1, max_length=2000)
    last_attempt_at: AwareDatetime | None = None
    last_success_at: AwareDatetime | None = None
    state: Literal["never_fetched", "ok", "error"]
    error: str | None = Field(default=None, max_length=500)
    item_count: int = Field(default=0, ge=0)
    next_fetch_at: AwareDatetime | None = None
    query_window_start: AwareDatetime | None = None
    query_window_end: AwareDatetime | None = None
    result_limit: int | None = Field(default=None, ge=1, le=250)
    possibly_truncated: bool = False
    query: str | None = Field(default=None, max_length=500)

    @field_validator("last_attempt_at", "last_success_at", "next_fetch_at", "query_window_start", "query_window_end")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @field_validator("feed_url", "terms_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        from app.news.urls import canonical_url
        return canonical_url(value)


class NewsResponse(NewsModel):
    edition: Literal["demo", "snapshot"]
    channel: Literal["news", "signals", "all"] = "all"
    as_of: AwareDatetime
    fetched_at: AwareDatetime | None
    last_attempt_at: AwareDatetime | None
    fetch_state: Literal["demo", "never_fetched", "ok", "error", "partial"]
    error: str | None = Field(default=None, max_length=500)
    events: list[NewsEvent] = Field(default_factory=list, max_length=500)
    duplicates_excluded: int = Field(default=0, ge=0)
    source_note: str = Field(min_length=1, max_length=2000)
    sources: list[NewsSourceStatus] = Field(default_factory=list, max_length=10)

    @field_validator("as_of", "fetched_at", "last_attempt_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value else None

    @model_validator(mode="after")
    def truthful_edition(self) -> "NewsResponse":
        demo = self.edition == "demo"
        if any(event.is_demo != demo for event in self.events):
            raise ValueError("Editions cannot mix synthetic and published events")
        if demo != (self.fetch_state == "demo"):
            raise ValueError("Demo edition must retain demo fetch state")
        if demo and (self.fetched_at or self.last_attempt_at):
            raise ValueError("Demo fixtures are not live fetches")
        if self.fetch_state == "never_fetched" and (self.events or self.fetched_at):
            raise ValueError("Never-fetched state cannot claim a stored observation")
        if self.fetch_state == "ok" and self.fetched_at is None:
            raise ValueError("Successful snapshot requires a retrieval timestamp")
        if len({event.id for event in self.events}) != len(self.events):
            raise ValueError("Event identities must be unique")
        if len({source.source_id for source in self.sources}) != len(self.sources):
            raise ValueError("Source health identities must be unique")
        article_ids = [article.id for event in self.events for article in event.articles]
        if len(set(article_ids)) != len(article_ids):
            raise ValueError("An article cannot inflate multiple event counts")
        return self
