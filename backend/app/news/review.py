"""Analyst placement reviews: confirm, move or remove an automatic news map position.

Reviews live in their own file beside the news snapshots, so a running poller never
overwrites them and they survive regrouping. They are written only by the operator CLI.
A review applies to whichever event currently contains its article. A confirmation
applies only while the automatic position is the one the analyst saw.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from pydantic import Field, ValidationError

from app.news.models import NewsEvent, NewsLocation, NewsModel, PlacementReview

MAX_REVIEWS = 2000
MAX_REVIEW_FILE_BYTES = 2 * 1024 * 1024


class ReviewError(ValueError):
    pass


class _ReviewFile(NewsModel):
    reviews: list[PlacementReview] = Field(default_factory=list, max_length=MAX_REVIEWS)


def reviews_path(news_path: Path | str) -> Path:
    path = Path(news_path)
    return path.with_name(f"{path.stem}.placement-reviews.json")


def load_reviews(news_path: Path | str) -> dict[str, PlacementReview]:
    path = reviews_path(news_path)
    try:
        if path.stat().st_size > MAX_REVIEW_FILE_BYTES:
            raise ReviewError("Placement review file exceeds its size limit")
        stored = _ReviewFile.model_validate_json(path.read_bytes())
    except FileNotFoundError:
        return {}
    except (OSError, ValidationError, UnicodeError) as error:
        raise ReviewError("Placement review file could not be read") from error
    return {review.article_url: review for review in stored.reviews}


def save_reviews(news_path: Path | str, reviews: dict[str, PlacementReview]) -> None:
    if len(reviews) > MAX_REVIEWS:
        raise ReviewError(f"At most {MAX_REVIEWS} placement reviews can be stored")
    path = reviews_path(news_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(reviews.values(), key=lambda review: (review.reviewed_at, review.article_url))
    body = _ReviewFile(reviews=ordered).model_dump_json(indent=2).encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix="reviews-", suffix=".tmp", dir=path.parent, delete=False) as target:
            temporary = Path(target.name)
            target.write(body)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def apply_review(event: NewsEvent, review: PlacementReview) -> NewsEvent:
    if review.action == "confirmed":
        if event.location is None or event.location.label != review.reviewed_label:
            return event  # The automatic position changed after the review; the confirmation no longer describes it.
        location = event.location.model_copy(update={
            "confidence": "medium",
            "basis": (f"{event.location.basis} An analyst ({review.reviewer}) checked this position against the sources on "
                      f"{_date(review.reviewed_at)}: {review.note}")[:1000]})
        return event.model_copy(update={"location": location, "placement_review": review})
    if review.action == "removed":
        return event.model_copy(update={"location": None, "scope": "unlocated", "placement_review": review})
    location = NewsLocation(
        lat=review.lat, lon=review.lon, label=f"{review.place_label} (analyst-set position)",
        precision="approximate_area", confidence="medium",
        basis=(f"An analyst ({review.reviewer}) set this position on {_date(review.reviewed_at)} after reading the sources: "
               f"{review.note} It is an analyst judgement, not an official incident location.")[:1000])
    return event.model_copy(update={"location": location, "scope": "located", "placement_review": review})


def apply_reviews(events: list[NewsEvent], reviews: dict[str, PlacementReview]) -> list[NewsEvent]:
    """Each event takes the newest review of any of its articles. Demo events are never reviewed."""
    if not reviews:
        return events
    reviewed = []
    for event in events:
        matches = [reviews[url] for article in event.articles if not article.is_demo
                   for url in (article.canonical_url, *article.duplicate_urls) if url in reviews]
        reviewed.append(apply_review(event, max(matches, key=lambda review: review.reviewed_at)) if matches else event)
    return reviewed


def describe(review: PlacementReview) -> dict:
    return json.loads(review.model_dump_json(exclude_none=True))
