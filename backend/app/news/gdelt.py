"""GDELT discovery metadata, never publisher publication dates or incident verification."""

from datetime import UTC, datetime
import hashlib
import json
import re
from urllib.parse import urlsplit

from app.news.models import NewsArticle, NewsEvent, NewsObservation
from app.news.service import MAX_FEED_BYTES, NewsError, _plain_text
from app.news.urls import canonical_url

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = "(airstrike OR \"missile strike\" OR \"drone attack\" OR bombing OR \"car bomb\" OR shelling OR explosion OR \"mass shooting\" OR \"terror attack\" OR coup OR riots OR earthquake OR wildfire OR flooding) sourcelang:english"
GDELT_LIMIT = 250


def article_clock(article: NewsArticle) -> datetime:
    return article.published_at or article.first_seen_at or article.retrieved_at


def merge_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Merge exact canonical URLs and provider observations; titles never identify an article."""
    groups: dict[str, list[NewsArticle]] = {}
    for article in articles:
        if article.is_demo or article.canonical_url is None:
            raise NewsError("Only attributed non-demo article URLs can be merged")
        groups.setdefault(canonical_url(article.canonical_url), []).append(article)
    merged = []
    for url, members in groups.items():
        # Prefer direct publisher metadata, which may supply publication dates and author credits.
        representative = min(members, key=lambda item: (item.published_at is None, item.source_id == "gdelt", item.id, item.model_dump_json()))
        observations = {}
        for item in members:
            for observation in item.observations:
                key = (observation.provider_id, observation.provider_timestamp, observation.language, observation.source_country)
                if key not in observations or observation.retrieved_at > observations[key].retrieved_at:
                    observations[key] = observation
        ordered = sorted(observations.values(), key=lambda item: (item.provider_timestamp or item.retrieved_at, item.provider_id,
                         item.language or "", item.source_country or "", item.provider_url), reverse=True)[:32]
        identity = hashlib.sha256(url.encode()).hexdigest()[:24]
        first_seen = min(item.first_seen_at or item.retrieved_at for item in members)
        merged.append(representative.model_copy(update={"id": f"article-{identity}", "canonical_url": url,
                      "first_seen_at": first_seen, "retrieved_at": max(item.retrieved_at for item in members),
                      "observations": ordered, "duplicate_urls": sorted({duplicate for item in members for duplicate in item.duplicate_urls})[:100]}))
    return sorted(merged, key=lambda item: (-article_clock(item).timestamp(), item.id))


def article_event(article: NewsArticle) -> NewsEvent:
    return NewsEvent(id=article.id.replace("article-", "event-", 1), title=article.headline, summary=article.summary,
                     category="world_news", status="reported", severity="unknown",
                     severity_basis="Discovery and publication metadata do not verify an incident or establish severity.",
                     grouping_basis="One canonical publisher article discovered by GDELT; no incident or geographic inference.",
                     grouping_status="single_source", location=None, scope="unlocated", is_demo=False, articles=[article])


def parse_gdelt_response(body: bytes, *, retrieved_at: datetime) -> tuple[list[NewsEvent], int]:
    if len(body) > MAX_FEED_BYTES:
        raise NewsError("GDELT response exceeds the 1 MiB limit")
    if not body.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"{"):
        # GDELT reports query problems as plain text with HTTP 200; surface that text to the operator.
        message = _plain_text(body[:400].decode("utf-8", "replace"), 200)
        raise NewsError(f"GDELT returned a message instead of article metadata: {message or 'empty response'}")
    try:
        def invalid_constant(value):
            raise ValueError("Invalid JSON numeric constant")
        data = json.loads(body.decode("utf-8-sig"), parse_constant=invalid_constant)
        if not isinstance(data, dict) or not isinstance(data.get("articles"), list) or len(data["articles"]) > GDELT_LIMIT:
            raise ValueError
        articles = []
        for record in data["articles"]:
            if not isinstance(record, dict) or any(not isinstance(record.get(key), str) for key in ("url", "title", "seendate")):
                raise ValueError
            url = canonical_url(record["url"])
            if (urlsplit(url).hostname or "").removeprefix("www.") == "gdacs.org" and urlsplit(url).path.lower() == "/report.aspx":
                continue  # Indexed official bulletins remain in the separate signals channel.
            headline = _plain_text(record["title"], 500)
            if not headline or not re.fullmatch(r"\d{8}T\d{6}Z", record["seendate"]):
                raise ValueError
            discovered = datetime.strptime(record["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            if discovered > retrieved_at:
                raise ValueError
            metadata = {}
            for field in ("language", "sourcecountry"):
                value = record.get(field)
                if value is not None and (not isinstance(value, str) or len(value) > 100):
                    raise ValueError
                metadata[field] = _plain_text(value, 100) if value else None
            publisher = (urlsplit(url).hostname or "").removeprefix("www.")
            observation = NewsObservation(provider_id="gdelt", provider_url=GDELT_URL,
                                          provider_timestamp=discovered, provider_timestamp_raw=record["seendate"], retrieved_at=retrieved_at,
                                          language=metadata["language"], source_country=metadata["sourcecountry"])
            identity = hashlib.sha256(url.encode()).hexdigest()[:24]
            articles.append(NewsArticle(id=f"article-{identity}", canonical_url=url, headline=headline,
                            publisher=publisher, publisher_id=publisher, source_id="gdelt", published_at=None,
                            first_seen_at=retrieved_at, retrieved_at=retrieved_at, observations=[observation], is_demo=False,
                            summary="GDELT returned this publisher article. Its seendate field is an unverified provider timestamp, not a publication date; consult the original source for context."))
        merged = merge_articles(articles)
        return [article_event(article) for article in merged], len(articles) - len(merged)
    except (ValueError, TypeError, UnicodeError, OverflowError) as error:
        raise NewsError("GDELT returned invalid article discovery metadata") from error
