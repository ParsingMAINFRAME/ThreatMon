"""Fixed public RSS sources, each with bounded fetches and an independent atomic JSON cache."""

import asyncio
from dataclasses import dataclass
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
from app.core.config import get_settings
from app.news.models import NewsArticle, NewsEvent, NewsModel, NewsResponse, NewsSourceStatus, NewsObservation
from app.news.urls import ArticleCandidate, canonical_url, deduplicate_articles

NASA_FEED_URL = "https://www.nasa.gov/feed/"
GLOBALVOICES_FEED_URL = "https://globalvoices.org/feed/"
GDACS_FEED_URL = "https://www.gdacs.org/xml/rss.xml"
MAX_FEED_BYTES = 1024 * 1024
MAX_CACHE_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 10
MIN_CACHE_SECONDS = 300
SOURCE_NOTE = ("NASA RSS article metadata, attributed to NASA; no endorsement is implied. Each article remains a separate "
               "reported publication with unknown incident severity and no inferred map coordinates. This is an operator-fetched "
               "snapshot, not continuous monitoring. fetched_at records the last successful retrieval or HTTP revalidation; "
               "article retrieved_at preserves body retrieval time. Time windows use the response as_of clock.")


@dataclass(frozen=True)
class SourceConfig:
    name: str
    kind: str
    feed_url: str
    terms_url: str
    attribution: str
    coverage_note: str
    cooldown: int


SOURCES = {
    "globalvoices": SourceConfig("Global Voices", "news", GLOBALVOICES_FEED_URL,
        "https://globalvoices.org/about/global-voices-attribution-policy/",
        "Global Voices and each named author; CC BY 3.0. Headlines and attribution only; no endorsement implied.",
        "At most 20 independent publisher articles. The RSS supplies no verified event association or incident coordinates; candidate associations and headline place markers are separate heuristics.", 900),
    "gdelt": SourceConfig("GDELT", "discovery", "https://api.gdeltproject.org/api/v2/doc/doc",
        "https://gdeltproject.org/about.html",
        "Discovery metadata provided by GDELT; article attribution belongs to each linked publisher. No article content licence or endorsement is implied.",
        "At most 250 collected canonical URLs retained for seven days after first ThreatMon collection. Query results may be capped and incomplete. seendate is an unverified provider timestamp, not publication. Publisher identity is a normalized URL hostname; publisher-country metadata is not incident geography.", 900),
    "wikipedia": SourceConfig("Wikipedia Current events", "discovery", "https://en.wikipedia.org/w/api.php",
        "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
        "Entry text by Wikipedia contributors, CC BY-SA 4.0, from the Current events portal; each entry links the first source it cites. No endorsement implied.",
        "Editor-curated entries for today and the two previous UTC days, at most 120. Entry text is Wikipedia's summary, not the linked publisher's headline. The portal day is an editor-chosen event day, not a publication time. Coverage reflects what volunteers have added and is incomplete.", 900),
    "gdacs": SourceConfig("GDACS", "official", GDACS_FEED_URL, "https://www.gdacs.org/About/termofuse.aspx",
        "GDACS / European Commission and United Nations. EU-owned content follows the linked Commission reuse policy; third-party rights remain separate. Metadata normalized; no endorsement implied.",
        "Only the latest 30 source events from available feed records are retained; this is not complete disaster coverage. Event IDs group revisions only. Source alert levels model potential humanitarian impact; reference points are approximate, and source date windows may include forecasts. Not population warnings.", 900),
    "nasa": SourceConfig("NASA", "news", NASA_FEED_URL, "https://www.nasa.gov/nasa-brand-center/images-and-media/",
        "NASA article metadata; no endorsement implied.", SOURCE_NOTE, 300),
}
NEWS_SOURCES = ("globalvoices", "gdelt", "wikipedia")
CHANNEL_SOURCES = {"news": NEWS_SOURCES, "signals": ("gdacs", "nasa"), "all": tuple(SOURCES)}
AGGREGATE_NOTE = ("Collected source metadata; no completeness guarantee. Polling runs only when an operator explicitly starts the CLI worker. "
                  "fetched_at is the latest successful retrieval or revalidation of ANY source; inspect each source's own status and clock. "
                  "Publication dates, where supplied, are not incident occurrence times. first_seen_at is first ThreatMon collection; provider timestamps retain their own provenance and uncertain meaning. "
                  "Source windows are source-provided periods, possibly forecasts. Time filters use the response as_of clock. "
                  "Candidate article associations are heuristics, not verified incidents or independent corroboration. A news marker is the reference point of a place named in a headline, "
                  "with low confidence; it is not a verified incident site. No article bodies or images are retained.")


class NewsError(ValueError):
    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


class NewsFileMissing(NewsError):
    pass


class NewsCache(NewsModel):
    response: NewsResponse
    etag: str | None = Field(default=None, max_length=1024)
    last_modified: str | None = Field(default=None, max_length=200)
    next_fetch_at: AwareDatetime
    query_watermark: AwareDatetime | None = None
    query_window_start: AwareDatetime | None = None
    query_window_end: AwareDatetime | None = None
    query: str | None = Field(default=None, max_length=500)
    watermark_query: str | None = Field(default=None, max_length=500)
    possibly_truncated: bool = False

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


def _rss_items(body: bytes) -> list[ElementTree.Element]:
    if len(body) > MAX_FEED_BYTES:
        raise NewsError("RSS feed exceeds the 1 MiB limit")
    try:
        # Decode before checking declarations. UTF-16/32 and NUL-containing XML cannot bypass the check.
        xml = body.decode("utf-8-sig")
        if "\x00" in xml or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.IGNORECASE):
            raise NewsError("XML document types and entities are not accepted")
        document = ElementTree.fromstring(xml)
    except (UnicodeDecodeError, ElementTree.ParseError) as error:
        raise NewsError("Feed is not valid UTF-8 RSS XML") from error
    if document.tag != "rss" or document.find("channel") is None:
        raise NewsError("Feed must be an RSS channel")
    items = document.findall("./channel/item")
    if not items:
        raise NewsError("Feed contains no usable records")
    return items


def parse_nasa_feed(body: bytes, *, retrieved_at: datetime) -> tuple[list[NewsEvent], int]:
    items = _rss_items(body)[:MAX_ITEMS]
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
            if published > retrieved_at:
                raise NewsError("NASA article publication time is unexpectedly in the future")
            headline = _plain_text(item.findtext("title") or "", 500)
            if not headline:
                raise NewsError("NASA article requires a headline")
            # Retain only headline/link/date metadata, never descriptions, article bodies, or media.
            summary = "NASA published this article. Consult the original source for its full context."
            identity = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
            article = NewsArticle(id=f"nasa-article-{identity}", canonical_url=url, headline=headline, publisher="NASA",
                                  published_at=published, retrieved_at=retrieved_at, summary=summary,
                                  observations=[NewsObservation(provider_id="nasa", provider_url=NASA_FEED_URL, retrieved_at=retrieved_at)],
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


def _empty(now: datetime, *, error: str | None = None, source: str = "nasa") -> NewsResponse:
    return NewsResponse(edition="snapshot", as_of=now, fetched_at=None, last_attempt_at=None,
                        fetch_state="error" if error else "never_fetched", error=error,
                        events=[], duplicates_excluded=0, source_note=SOURCES[source].coverage_note)


def _load_cache(path: Path, source: str = "nasa") -> NewsCache | None:
    try:
        with path.open("rb") as cache_file:
            body = cache_file.read(MAX_CACHE_BYTES + 1)
        if len(body) > MAX_CACHE_BYTES:
            raise NewsError("Stored news snapshot exceeds its size limit")
        cache = NewsCache.model_validate_json(body)
        if cache.response.edition != "snapshot":
            raise NewsError("Stored news snapshot has an invalid edition")
        if cache.response.fetch_state not in {"never_fetched", "ok", "error"} or any(
            article.source_id != source for event in cache.response.events for article in event.articles
        ):
            raise NewsError("Stored news snapshot has an invalid source identity")
        return cache
    except FileNotFoundError:
        return None
    except (OSError, ValidationError) as error:
        raise NewsError("Stored news snapshot could not be read") from error


def source_cache_path(path: Path | str, source: str) -> Path:
    if source not in SOURCES:
        raise ValueError("Unknown news source")
    path = Path(path)
    return path if source == "nasa" else path.with_name(f"{path.stem}.{source}{path.suffix or '.json'}")


def _with_status(response: NewsResponse, source: str, next_fetch_at: datetime | None = None, cache: NewsCache | None = None) -> NewsResponse:
    config = SOURCES[source]
    status = NewsSourceStatus(source_id=source, publisher_id=source, name=config.name, kind=config.kind,
                              feed_url=config.feed_url, terms_url=config.terms_url, attribution=config.attribution,
                              coverage_note=config.coverage_note, last_attempt_at=response.last_attempt_at,
                              last_success_at=response.fetched_at, state=response.fetch_state, error=response.error,
                              item_count=sum(len(event.articles) for event in response.events), next_fetch_at=next_fetch_at,
                              query_window_start=cache.query_window_start if cache else None,
                              query_window_end=cache.query_window_end if cache else None,
                              query=cache.query if cache else get_settings().news_gdelt_query if source == "gdelt" else None,
                              result_limit=250 if source == "gdelt" else None,
                              possibly_truncated=cache.possibly_truncated if cache else False)
    return response.model_copy(update={"sources": [status]})


def read_news(path: Path | str, *, now: datetime | None = None, source: str = "nasa") -> NewsResponse:
    now = now or utc_now()
    path = source_cache_path(path, source)
    try:
        cache = _load_cache(path, source)
        response = cache.response.model_copy(update={"as_of": now}) if cache else _empty(now, source=source)
        return _with_status(response, source, cache.next_fetch_at if cache else None, cache)
    except NewsError as error:
        return _with_status(_empty(now, error=str(error), source=source), source)


def _aggregate(responses: list[NewsResponse], now: datetime, channel: str = "all") -> NewsResponse:
    from app.news.gdelt import article_clock, merge_articles
    from app.news.grouping import group_candidate_events
    sources = [status for response in responses for status in response.sources]
    states = {status.state for status in sources}
    state = "ok" if states == {"ok"} else "partial" if "ok" in states else "error" if "error" in states else "never_fetched"
    successes = [status.last_success_at for status in sources if status.last_success_at]
    attempts = [status.last_attempt_at for status in sources if status.last_attempt_at]
    errors = [f"{status.name}: {status.error}" for status in sources if status.error]
    source_events = [event for response in responses for event in response.events]
    news_articles = [article for event in source_events for article in event.articles if article.source_id in NEWS_SOURCES]
    events = [event for event in source_events if all(article.source_id not in NEWS_SOURCES for article in event.articles)]
    merged = merge_articles(news_articles)
    events.extend(group_candidate_events(merged, previous_events=source_events))
    events.sort(key=lambda event: (-max(article_clock(article) for article in event.articles).timestamp(), event.id))
    return NewsResponse(edition="snapshot", as_of=now, fetched_at=max(successes) if successes else None,
                        last_attempt_at=max(attempts) if attempts else None, fetch_state=state,
                        error="; ".join(errors)[:500] if errors else None, events=events,
                        duplicates_excluded=sum(response.duplicates_excluded for response in responses) + len(news_articles) - len(merged),
                        source_note=AGGREGATE_NOTE, sources=sources, channel=channel)


def read_sources(path: Path | str, *, now: datetime | None = None, channel: str = "news") -> NewsResponse:
    if channel not in CHANNEL_SOURCES:
        raise ValueError("Unknown news channel")
    now = now or utc_now()
    return _aggregate([read_news(path, now=now, source=source) for source in CHANNEL_SOURCES[channel]], now, channel)


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


def _cache_seconds(headers: httpx.Headers, minimum: int = MIN_CACHE_SECONDS) -> int:
    match = re.search(r"(?:^|,)\s*max-age\s*=\s*(\d{1,9})(?:\s*,|\s*$)", headers.get("cache-control", ""), re.IGNORECASE)
    return max(minimum, int(match[1]) if match else 0)


def _next_fetch(now: datetime, seconds: int) -> datetime:
    maximum = int((datetime.max.replace(tzinfo=UTC) - now).total_seconds()) - 1
    return now + timedelta(seconds=min(max(MIN_CACHE_SECONDS, seconds), maximum))


async def _fetch(client: httpx.AsyncClient, cache: NewsCache | None, now: datetime, source: str = "nasa") -> tuple[bytes | None, httpx.Headers]:
    config = SOURCES[source]
    url = config.feed_url
    headers = {"User-Agent": "ThreatMon/0.3 (read-only RSS portfolio client)", "Accept": "application/rss+xml, application/xml, text/xml"}
    if source == "wikipedia":
        from app.news.wikipedia import request_url
        url = request_url(now)
        headers = {"User-Agent": "ThreatMon/0.4 (https://github.com/ParsingMAINFRAME/ThreatMon; read-only metadata client)", "Accept": "application/json"}
    if cache and cache.response.fetched_at:
        if cache.etag:
            headers["If-None-Match"] = cache.etag
        if cache.last_modified:
            headers["If-Modified-Since"] = cache.last_modified
    async with asyncio.timeout(45):
        for attempt in range(3):
            try:
                async with client.stream("GET", url, headers=headers, timeout=15, follow_redirects=False) as response:
                    if response.status_code == 304:
                        if cache is None or cache.response.fetched_at is None:
                            raise NewsError(f"{config.name} returned an unchanged response without a cached snapshot")
                        return None, response.headers
                    if response.status_code != 200:
                        retry_after = _retry_after(response.headers.get("retry-after"), now)
                        if (response.status_code >= 500 or response.status_code == 429) and attempt < 2 and not retry_after:
                            await asyncio.sleep(0.25 * 2 ** attempt)
                            continue
                        raise NewsError(f"{config.name} feed returned HTTP {response.status_code}", retry_after)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_FEED_BYTES:
                            raise NewsError(f"{config.name} feed exceeds the 1 MiB limit")
                    return bytes(body), response.headers
            except httpx.TransportError as error:
                if attempt < 2:
                    await asyncio.sleep(0.25 * 2 ** attempt)
                    continue
                raise NewsError(f"{config.name} feed transport failed after bounded retries") from error
    raise NewsError(f"{config.name} feed request failed")


async def ingest_news(path: Path | str, *, client: httpx.AsyncClient | None = None, now: datetime | None = None,
                      source: str = "nasa") -> NewsResponse:
    if source == "gdelt":
        return await ingest_gdelt(path, client=client, now=now)
    base = Path(path)
    path = source_cache_path(base, source)
    config = SOURCES[source]
    now = now or utc_now()
    try:
        cache = _load_cache(path, source)
    except NewsError:
        cache = None
    previous = cache.response if cache else _empty(now, source=source)
    if cache and now < cache.next_fetch_at:
        return _with_status(previous.model_copy(update={"as_of": now}), source, cache.next_fetch_at)
    if client is None:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as owned_client:
            return await ingest_news(base, client=owned_client, now=now, source=source)
    cache_seconds = config.cooldown
    try:
        from app.news.feeds import parse_gdacs_feed, parse_globalvoices_feed
        from app.news.wikipedia import parse_current_events
        parser = {"nasa": parse_nasa_feed, "globalvoices": parse_globalvoices_feed, "gdacs": parse_gdacs_feed,
                  "wikipedia": parse_current_events}[source]
        body, headers = await _fetch(client, cache, now, source)
        events, excluded = parser(body, retrieved_at=now) if body is not None else (previous.events, previous.duplicates_excluded)
        result = NewsResponse(edition="snapshot", as_of=now, fetched_at=now, last_attempt_at=now, fetch_state="ok",
                              error=None, events=events, duplicates_excluded=excluded, source_note=config.coverage_note)
        cache_seconds = _cache_seconds(headers, config.cooldown)
        result = _with_status(result, source, _next_fetch(now, cache_seconds))
        stored = NewsCache(response=result, etag=headers.get("etag") or (cache.etag if cache and body is None else None),
                           last_modified=headers.get("last-modified") or (cache.last_modified if cache and body is None else None),
                           next_fetch_at=_next_fetch(now, cache_seconds))
    except (NewsError, TimeoutError, ValidationError, httpx.HTTPError) as error:
        message = str(error) if isinstance(error, NewsError) else f"{config.name} retrieval failed; retained snapshot preserved"
        cache_seconds = max(config.cooldown, getattr(error, "retry_after", 0))
        result = previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error", "error": message[:500]})
        result = _with_status(result, source, _next_fetch(now, cache_seconds))
        stored = NewsCache(response=result, etag=cache.etag if cache else None,
                           last_modified=cache.last_modified if cache else None, next_fetch_at=_next_fetch(now, cache_seconds))
    try:
        _save_cache(path, stored)
    except (OSError, NewsError):
        return _with_status(previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error",
                                           "error": "Could not save news cache; previous disk snapshot remains unchanged"}),
                            source, cache.next_fetch_at if cache else None)
    return result


async def ingest_sources(path: Path | str, *, source: str = "all", client: httpx.AsyncClient | None = None,
                         now: datetime | None = None) -> NewsResponse:
    if source != "all" and source not in SOURCES:
        raise ValueError("Unknown news source")
    now = now or utc_now()
    selected = list(SOURCES) if source == "all" else [source]
    if client is None:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as owned_client:
            return await ingest_sources(path, source=source, client=owned_client, now=now)
    # Different source paths and cooldowns make the three bounded operations independent.
    fetched = await asyncio.gather(*(ingest_news(path, source=name, client=client, now=now) for name in selected))
    responses = dict(zip(selected, fetched))
    return _aggregate([responses[name] if name in responses else read_news(path, source=name, now=now) for name in SOURCES], now)


async def ingest_gdelt(path: Path | str, *, client: httpx.AsyncClient | None = None,
                       now: datetime | None = None) -> NewsResponse:
    """One request per import; preserve good metadata and query progress independently."""
    if get_settings().news_gdelt_mode == "bulk":
        return await ingest_gdelt_bulk(path, client=client, now=now)
    from app.news.gdelt import GDELT_URL, GDELT_LIMIT, merge_articles, parse_gdelt_response
    from app.news.grouping import group_candidate_events
    now = now or utc_now()
    base = Path(path)
    target = source_cache_path(base, "gdelt")
    try:
        cache = _load_cache(target, "gdelt")
    except NewsError:
        cache = None
    previous = cache.response if cache else _empty(now, source="gdelt")
    if cache and now < cache.next_fetch_at:
        return _with_status(previous.model_copy(update={"as_of": now}), "gdelt", cache.next_fetch_at, cache)
    if client is None:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as owned_client:
            return await ingest_gdelt(base, client=owned_client, now=now)
    query = get_settings().news_gdelt_query
    end = now.replace(microsecond=0)
    watermark = cache.query_watermark if cache and cache.watermark_query == query else None
    desired_start = watermark - timedelta(minutes=15) if watermark else end - timedelta(hours=24)
    start = max(desired_start, end - timedelta(days=7))
    # A backwards system clock never produces a reversed request window.
    start = min(start, end - timedelta(minutes=15))
    truncated = bool(cache and cache.possibly_truncated) or start > desired_start
    parameters = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": str(GDELT_LIMIT),
                  "sort": "DateDesc", "startdatetime": start.strftime("%Y%m%d%H%M%S"),
                  "enddatetime": end.strftime("%Y%m%d%H%M%S")}
    cooldown = 900
    try:
        async with asyncio.timeout(45):
            async with client.stream("GET", GDELT_URL, params=parameters,
                                     headers={"User-Agent": "ThreatMon/0.4 (bounded metadata portfolio client)", "Accept": "application/json"},
                                     timeout=15, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise NewsError(f"GDELT returned HTTP {response.status_code}; no immediate retry", _retry_after(response.headers.get("retry-after"), now))
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_FEED_BYTES:
                        raise NewsError("GDELT response exceeds the 1 MiB limit")
                cooldown = _cache_seconds(response.headers, 900)
        new_events, excluded = parse_gdelt_response(bytes(body), retrieved_at=now)
        new_articles = [article for event in new_events for article in event.articles]
        existing = [article for event in previous.events for article in event.articles]
        combined = merge_articles([*existing, *new_articles])
        recent = [article for article in combined if (article.first_seen_at or article.retrieved_at) >= now - timedelta(days=7)]
        recent.sort(key=lambda article: (-(article.first_seen_at or article.retrieved_at).timestamp(), article.id))
        # Raw count reaching the provider cap leaves completeness unknown even after deduplication.
        import json
        truncated = truncated or len(json.loads(body)["articles"]) == GDELT_LIMIT or len(recent) > GDELT_LIMIT
        events = group_candidate_events(recent[:GDELT_LIMIT], previous_events=previous.events)
        result = NewsResponse(edition="snapshot", as_of=now, fetched_at=now, last_attempt_at=now, fetch_state="ok",
                              events=events, duplicates_excluded=excluded, source_note=SOURCES["gdelt"].coverage_note)
        stored = NewsCache(response=result, next_fetch_at=_next_fetch(now, cooldown), query_watermark=end,
                           query_window_start=start, query_window_end=end, query=query, watermark_query=query,
                           possibly_truncated=truncated)
    except (NewsError, TimeoutError, ValidationError, httpx.HTTPError) as error:
        message = str(error) if isinstance(error, NewsError) else "GDELT request failed; retained metadata preserved; no immediate retry"
        cooldown = max(900, getattr(error, "retry_after", 0))
        result = previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error", "error": message[:500]})
        stored = NewsCache(response=result, next_fetch_at=_next_fetch(now, cooldown),
                           query_watermark=cache.query_watermark if cache else None,
                           watermark_query=cache.watermark_query if cache else None,
                           query_window_start=start, query_window_end=end, query=query, possibly_truncated=truncated)
    result = _with_status(result, "gdelt", stored.next_fetch_at, stored)
    stored.response = result
    try:
        _save_cache(target, stored)
    except (OSError, NewsError):
        return _with_status(previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error",
                            "error": "Could not save GDELT cache; previous disk snapshot remains unchanged"}),
                            "gdelt", cache.next_fetch_at if cache else None, cache)
    return result


async def _download(client: httpx.AsyncClient, url: str, limit: int, now: datetime) -> bytes:
    async with client.stream("GET", url, headers={"User-Agent": "ThreatMon/0.4 (https://github.com/ParsingMAINFRAME/ThreatMon; bounded metadata client)"},
                             timeout=30, follow_redirects=False) as response:
        if response.status_code == 404:
            raise NewsFileMissing("GDELT file server returned HTTP 404; no immediate retry")
        if response.status_code != 200:
            raise NewsError(f"GDELT file server returned HTTP {response.status_code}; no immediate retry", _retry_after(response.headers.get("retry-after"), now))
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > limit:
                raise NewsError("GDELT file exceeds its download limit")
        return bytes(body)


async def ingest_gdelt_bulk(path: Path | str, *, client: httpx.AsyncClient | None = None,
                            now: datetime | None = None) -> NewsResponse:
    """Read the newest published 15-minute files; at most four per import, never the search API."""
    from app.news.gdelt import GDELT_LIMIT, merge_articles
    from app.news.gdelt_bulk import BULK_QUERY, LASTUPDATE_URL, MAX_ZIP_BYTES, file_times, file_url, latest_file_time, parse_gkg_file
    from app.news.grouping import group_candidate_events
    now = now or utc_now()
    base = Path(path)
    target = source_cache_path(base, "gdelt")
    try:
        cache = _load_cache(target, "gdelt")
    except NewsError:
        cache = None
    previous = cache.response if cache else _empty(now, source="gdelt")
    if cache and now < cache.next_fetch_at:
        return _with_status(previous.model_copy(update={"as_of": now}), "gdelt", cache.next_fetch_at, cache)
    if client is None:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as owned_client:
            return await ingest_gdelt_bulk(base, client=owned_client, now=now)
    watermark = cache.query_watermark if cache and cache.watermark_query == BULK_QUERY else None
    start = end = None
    truncated = bool(cache and cache.possibly_truncated and cache.watermark_query == BULK_QUERY)
    try:
        async with asyncio.timeout(150):
            latest = latest_file_time(await _download(client, LASTUPDATE_URL, 4096, now))
            if latest > now + timedelta(minutes=15):
                raise NewsError("GDELT listed a file dated in the future")
            times, skipped = file_times(latest, watermark)
            new_articles = []
            read_times = []
            for time in times:
                try:
                    body = await _download(client, file_url(time), MAX_ZIP_BYTES, now)
                except NewsFileMissing:
                    continue  # The newest listed file is often not uploaded yet; the others are still read.
                new_articles.extend(parse_gkg_file(body, file_time=time, retrieved_at=now))
                read_times.append(time)
        if read_times:
            start, end = read_times[0] - timedelta(minutes=15), read_times[-1]
            # A missing file older than one that was read is a real gap; a missing newest file is retried next import.
            skipped = skipped or any(time < read_times[-1] and time not in read_times for time in times)
            latest = read_times[-1]
        else:
            start, end = (cache.query_window_start, cache.query_window_end) if cache else (None, None)
            latest = watermark
        existing = [article for event in previous.events for article in event.articles]
        combined = merge_articles([*existing, *new_articles])
        recent = [article for article in combined if (article.first_seen_at or article.retrieved_at) >= now - timedelta(days=7)]
        recent.sort(key=lambda article: (-(article.first_seen_at or article.retrieved_at).timestamp(), article.id))
        # Skipped older files or a full retention window leave completeness unknown.
        truncated = truncated or skipped or len(recent) > GDELT_LIMIT
        events = group_candidate_events(recent[:GDELT_LIMIT], previous_events=previous.events)
        result = NewsResponse(edition="snapshot", as_of=now, fetched_at=now, last_attempt_at=now, fetch_state="ok",
                              events=events, duplicates_excluded=len(existing) + len(new_articles) - len(combined),
                              source_note=SOURCES["gdelt"].coverage_note)
        stored = NewsCache(response=result, next_fetch_at=_next_fetch(now, 900), query_watermark=latest,
                           query_window_start=start, query_window_end=end, query=BULK_QUERY, watermark_query=BULK_QUERY,
                           possibly_truncated=truncated)
    except (NewsError, TimeoutError, ValidationError, httpx.HTTPError) as error:
        message = str(error) if isinstance(error, NewsError) else "GDELT file retrieval failed; retained metadata preserved; no immediate retry"
        cooldown = max(900, getattr(error, "retry_after", 0))
        result = previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error", "error": message[:500]})
        stored = NewsCache(response=result, next_fetch_at=_next_fetch(now, cooldown),
                           query_watermark=cache.query_watermark if cache else None,
                           watermark_query=cache.watermark_query if cache else None,
                           query_window_start=cache.query_window_start if cache else None,
                           query_window_end=cache.query_window_end if cache else None,
                           query=cache.query if cache else BULK_QUERY, possibly_truncated=truncated)
    result = _with_status(result, "gdelt", stored.next_fetch_at, stored)
    stored.response = result
    try:
        _save_cache(target, stored)
    except (OSError, NewsError):
        return _with_status(previous.model_copy(update={"as_of": now, "last_attempt_at": now, "fetch_state": "error",
                            "error": "Could not save GDELT cache; previous disk snapshot remains unchanged"}),
                            "gdelt", cache.next_fetch_at if cache else None, cache)
    return result
