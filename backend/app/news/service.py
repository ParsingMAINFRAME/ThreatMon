"""A single fixed public RSS source with bounded fetches and an atomic local JSON cache."""

import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx
from pydantic import AwareDatetime, Field, ValidationError, field_validator

from app.core.time import utc_now
from app.news.models import NewsArticle, NewsEvent, NewsModel, NewsResponse
from app.news.urls import ArticleCandidate, canonical_url, deduplicate_articles

NASA_FEED_URL = "https://www.nasa.gov/feed/"
MAX_FEED_BYTES = 1024 * 1024
MAX_CACHE_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 10
MIN_CACHE_SECONDS = 300
SOURCE_NOTE = ("NASA RSS article metadata, attributed to NASA; no endorsement is implied. Each article remains a separate "
               "reported publication with unknown incident severity and no inferred map coordinates. This is an operator-fetched "
               "snapshot, not continuous monitoring. fetched_at records the last successful retrieval or HTTP revalidation; "
               "article retrieved_at preserves body retrieval time. Time windows use the response as_of clock.")


class NewsError(ValueError):
    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


class NewsCache(NewsModel):
    response: NewsResponse
    etag: str | None = Field(default=None, max_length=1024)
    last_modified: str | None = Field(default=None, max_length=200)
    next_fetch_at: AwareDatetime

    @field_validator("etag", "last_modified")
    @classmethod
    def safe_header(cls, value: str | None) -> str | None:
        if value is not None and any(ord(character) < 32 or ord(character) > 126 for character in value):
            raise ValueError("Invalid cached conditional header")
        return value


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe"}:
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe"} and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def _plain_text(value: str, limit: int) -> str:
    parser = _PlainText()
    parser.feed(value[:30_000])
    return " ".join(" ".join(parser.parts).split())[:limit]


def parse_nasa_feed(body: bytes, *, retrieved_at: datetime) -> tuple[list[NewsEvent], int]:
    if len(body) > MAX_FEED_BYTES:
        raise NewsError("NASA feed exceeds the 1 MiB limit")
    try:
        # Decode before checking declarations. UTF-16/32 and NUL-containing XML cannot bypass the check.
        xml = body.decode("utf-8-sig")
        if "\x00" in xml or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.IGNORECASE):
            raise NewsError("XML document types and entities are not accepted")
        document = ElementTree.fromstring(xml)
    except (UnicodeDecodeError, ElementTree.ParseError) as error:
        raise NewsError("NASA feed is not valid UTF-8 RSS XML") from error
    if document.tag != "rss" or document.find("channel") is None:
        raise NewsError("NASA feed must be an RSS channel")
    items = document.findall("./channel/item")[:MAX_ITEMS]
    if not items:
        raise NewsError("NASA feed contains no usable articles")
    candidates = []
    for item in items:
        try:
            url = canonical_url((item.findtext("link") or "").strip())
            host = urlsplit(url).hostname or ""
            if urlsplit(url).scheme != "https" or not (host == "nasa.gov" or host.endswith(".nasa.gov")):
                raise NewsError("NASA article URL must use an official HTTPS nasa.gov domain")
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                raise NewsError("NASA article date must include a timezone")
            published = published.astimezone(UTC)
            if published > retrieved_at + timedelta(minutes=5):
                raise NewsError("NASA article publication time is unexpectedly in the future")
            headline = _plain_text(item.findtext("title") or "", 500)
            if not headline:
                raise NewsError("NASA article requires a headline")
            # Retain only headline/link/date metadata, never descriptions, article bodies, or media.
            summary = "NASA published this article. Consult the original source for its full context."
            identity = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
            article = NewsArticle(id=f"nasa-article-{identity}", canonical_url=url, headline=headline, publisher="NASA",
                                  published_at=published, retrieved_at=retrieved_at, summary=summary,
                                  is_demo=False, syndication_key=None, duplicate_urls=[])
            candidates.append(ArticleCandidate(article))
        except NewsError:
            raise
        except (ValueError, TypeError, OverflowError) as error:
            raise NewsError("NASA article has invalid URL, date, or metadata") from error
    articles, excluded = deduplicate_articles(candidates)
    events = [NewsEvent(id=article.id.replace("nasa-article-", "nasa-event-"), title=article.headline,
                        summary=article.summary, category="space_planetary", status="reported", severity="unknown",
                        severity_basis="This RSS publication supplies no validated incident severity; publication volume is not severity.",
                        grouping_basis="One canonical NASA article per event; no country, keyword, title-similarity, or coordinate clustering.",
                        location=None, scope="unlocated", is_demo=False, articles=[article]) for article in articles]
    return events, excluded


def _empty(now: datetime, *, error: str | None = None) -> NewsResponse:
    return NewsResponse(edition="snapshot", as_of=now, fetched_at=None, last_attempt_at=None,
                        fetch_state="error" if error else "never_fetched", error=error,
                        events=[], duplicates_excluded=0, source_note=SOURCE_NOTE)


def _load_cache(path: Path) -> NewsCache | None:
    try:
        with path.open("rb") as source:
            body = source.read(MAX_CACHE_BYTES + 1)
        if len(body) > MAX_CACHE_BYTES:
            raise NewsError("Stored news snapshot exceeds its size limit")
        cache = NewsCache.model_validate_json(body)
        if cache.response.edition != "snapshot":
            raise NewsError("Stored news snapshot has an invalid edition")
        return cache
    except FileNotFoundError:
        return None
    except (OSError, ValidationError) as error:
        raise NewsError("Stored news snapshot could not be read") from error


def read_news(path: Path | str, *, now: datetime | None = None) -> NewsResponse:
    now = now or utc_now()
    try:
        cache = _load_cache(Path(path))
        return cache.response.model_copy(update={"as_of": now}) if cache else _empty(now)
    except NewsError as error:
        return _empty(now, error=str(error))


def _save_cache(path: Path, cache: NewsCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = cache.model_dump_json(indent=2).encode("utf-8")
    if len(body) > MAX_CACHE_BYTES:
        raise NewsError("News snapshot exceeds its storage limit")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix="news-", suffix=".tmp", dir=path.parent, delete=False) as target:
            temporary = Path(target.name)
            target.write(body)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _retry_after(value: str | None, now: datetime) -> int:
    if not value:
        return 0
    if re.fullmatch(r"\d{1,9}", value.strip()):
        return int(value)
    try:
        parsed = parsedate_to_datetime(value)
        return max(0, int((parsed.astimezone(UTC) - now).total_seconds())) if parsed.tzinfo else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def _cache_seconds(headers: httpx.Headers) -> int:
    match = re.search(r"(?:^|,)\s*max-age\s*=\s*(\d{1,9})(?:\s*,|\s*$)", headers.get("cache-control", ""), re.IGNORECASE)
    return max(MIN_CACHE_SECONDS, int(match[1]) if match else 0)


def _next_fetch(now: datetime, seconds: int) -> datetime:
    maximum = int((datetime.max.replace(tzinfo=UTC) - now).total_seconds()) - 1
    return now + timedelta(seconds=min(max(MIN_CACHE_SECONDS, seconds), maximum))


async def _fetch(client: httpx.AsyncClient, cache: NewsCache | None, now: datetime) -> tuple[bytes | None, httpx.Headers]:
    headers = {"User-Agent": "ThreatMon/0.3 (read-only NASA RSS portfolio client)", "Accept": "application/rss+xml, application/xml, text/xml"}
    if cache and cache.response.fetched_at:
        if cache.etag:
            headers["If-None-Match"] = cache.etag
        if cache.last_modified:
            headers["If-Modified-Since"] = cache.last_modified
    async with asyncio.timeout(45):
        for attempt in range(3):
            try:
                async with client.stream("GET", NASA_FEED_URL, headers=headers, timeout=15, follow_redirects=False) as response:
                    if response.status_code == 304:
                        if cache is None or cache.response.fetched_at is None:
                            raise NewsError("NASA returned an unchanged response without a cached snapshot")
                        return None, response.headers
                    if response.status_code != 200:
                        retry_after = _retry_after(response.headers.get("retry-after"), now)
                        if (response.status_code >= 500 or response.status_code == 429) and attempt < 2 and not retry_after:
                            await asyncio.sleep(0.25 * 2 ** attempt)
                            continue
                        raise NewsError(f"NASA feed returned HTTP {response.status_code}", retry_after)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_FEED_BYTES:
                            raise NewsError("NASA feed exceeds the 1 MiB limit")
                    return bytes(body), response.headers
            except httpx.TransportError as error:
                if attempt < 2:
                    await asyncio.sleep(0.25 * 2 ** attempt)
                    continue
                raise NewsError("NASA feed transport failed after bounded retries") from error
    raise NewsError("NASA feed request failed")


async def ingest_news(path: Path | str, *, client: httpx.AsyncClient | None = None, now: datetime | None = None) -> NewsResponse:
    path = Path(path)
    now = now or utc_now()
    try:
        cache = _load_cache(path)
    except NewsError:
        cache = None
    previous = cache.response if cache else _empty(now)
    if cache and now < cache.next_fetch_at:
        return previous.model_copy(update={"as_of": now})
    if client is None:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as owned_client:
            return await ingest_news(path, client=owned_client, now=now)
    cache_seconds = MIN_CACHE_SECONDS
    try:
        body, headers = await _fetch(client, cache, now)
        events, excluded = parse_nasa_feed(body, retrieved_at=now) if body is not None else (previous.events, previous.duplicates_excluded)
        result = NewsResponse(edition="snapshot", as_of=now, fetched_at=now, last_attempt_at=now, fetch_state="ok",
                              error=None, events=events, duplicates_excluded=excluded, source_note=SOURCE_NOTE)
        cache_seconds = _cache_seconds(headers)
        stored = NewsCache(response=result, etag=headers.get("etag") or (cache.etag if cache and body is None else None),
                           last_modified=headers.get("last-modified") or (cache.last_modified if cache and body is None else None),
                           next_fetch_at=_next_fetch(now, cache_seconds))
    except (NewsError, TimeoutError, ValidationError, httpx.HTTPError) as error:
        message = str(error) if isinstance(error, NewsError) else "NASA news retrieval failed; retained snapshot preserved"
        cache_seconds = max(MIN_CACHE_SECONDS, getattr(error, "retry_after", 0))
        result = previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error", "error": message[:500]})
        stored = NewsCache(response=result, etag=cache.etag if cache else None,
                           last_modified=cache.last_modified if cache else None, next_fetch_at=_next_fetch(now, cache_seconds))
    try:
        _save_cache(path, stored)
    except (OSError, NewsError):
        return previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error",
                                           "error": "Could not save news cache; previous disk snapshot remains unchanged"})
    return result
