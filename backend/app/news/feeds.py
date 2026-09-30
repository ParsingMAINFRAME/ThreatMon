"""Metadata-only public RSS adapters; publication identity is never inferred from prose."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import hashlib
import math
import re
from urllib.parse import parse_qs, urlsplit

from app.news.models import NewsArticle, NewsEvent, NewsLocation, NewsObservation
from app.news.service import NewsError, _plain_text, _rss_items
from app.news.urls import ArticleCandidate, canonical_url, deduplicate_articles

DC = "{http://purl.org/dc/elements/1.1/}"
GDACS = "{http://www.gdacs.org}"
GEORSS = "{http://www.georss.org/georss}"
GV_LICENSE = "https://creativecommons.org/licenses/by/3.0/"
HAZARDS = {"EQ": "earthquake", "FL": "flood", "TC": "tropical_cyclone", "DR": "drought",
           "WF": "wildfire", "VO": "volcano"}


def _date(value: str, *, now: datetime | None = None) -> datetime:
    try:
        result = parsedate_to_datetime(value)
        if result.tzinfo is None:
            raise ValueError
        result = result.astimezone(UTC)
        if now is not None and result > now:
            raise ValueError
        return result
    except (ValueError, TypeError, OverflowError) as error:
        raise NewsError("RSS date is invalid, lacks a timezone, or publication is in the future") from error


def _url(value: str, hosts: set[str]) -> str:
    try:
        result = canonical_url(value.strip())
        parsed = urlsplit(result)
        if parsed.scheme != "https" or parsed.hostname not in hosts:
            raise ValueError
        return result
    except ValueError as error:
        raise NewsError("RSS source URL is outside its allowed HTTPS publisher hosts") from error


def parse_globalvoices_feed(body: bytes, *, retrieved_at: datetime) -> tuple[list[NewsEvent], int]:
    candidates = []
    for item in _rss_items(body):
        url = _url(item.findtext("link") or "", {"globalvoices.org", "www.globalvoices.org"})
        headline = _plain_text(item.findtext("title") or "", 500)
        if not headline:
            raise NewsError("Global Voices article requires a headline")
        published = _date(item.findtext("pubDate") or "", now=retrieved_at)
        author = _plain_text(item.findtext(DC + "creator") or "", 301)
        if not author or len(author) > 300:
            raise NewsError("Global Voices article requires a complete author credit of at most 300 characters")
        identity = hashlib.sha256(url.encode()).hexdigest()[:24]
        article = NewsArticle(id=f"globalvoices-article-{identity}", canonical_url=url, headline=headline,
                              publisher="Global Voices", source_id="globalvoices", publisher_id="globalvoices",
                              author=author, license_url=GV_LICENSE, published_at=published, retrieved_at=retrieved_at,
                              observations=[NewsObservation(provider_id="globalvoices", provider_url="https://globalvoices.org/feed/", retrieved_at=retrieved_at)],
                              summary="Global Voices published this article. Consult the original source for its full context.",
                              is_demo=False)
        candidates.append(ArticleCandidate(article))
    articles, excluded = deduplicate_articles(candidates)
    articles.sort(key=lambda item: (-item.published_at.timestamp(), item.id))
    events = [NewsEvent(id=article.id.replace("-article-", "-event-"), title=article.headline,
                        summary=article.summary, category="world_news", status="reported", severity="unknown",
                        severity_basis="Publication is not verification of every claim and does not establish incident severity.",
                        grouping_basis="One canonical Global Voices article; no inferred grouping, corroboration, or geographic location.",
                        location=None, scope="unlocated", is_demo=False, articles=[article]) for article in articles[:20]]
    return events, excluded


def parse_gdacs_feed(body: bytes, *, retrieved_at: datetime) -> tuple[list[NewsEvent], int]:
    retained: dict[str, tuple[tuple, NewsEvent]] = {}
    items = _rss_items(body)
    for item in items:
        eventtype = (item.findtext(GDACS + "eventtype") or "").strip()
        eventid = (item.findtext(GDACS + "eventid") or "").strip()
        episode = (item.findtext(GDACS + "episodeid") or "").strip()
        if eventtype not in HAZARDS or not re.fullmatch(r"[0-9]{1,20}", eventid) or not re.fullmatch(r"[0-9]{1,20}", episode):
            raise NewsError("GDACS record requires recognized hazard, event and episode identifiers")
        url = _url(item.findtext("link") or "", {"gdacs.org", "www.gdacs.org"})
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.path.lower() != "/report.aspx" or query.get("eventtype") != [eventtype] or query.get("eventid") != [eventid]:
            raise NewsError("GDACS report URL does not match its source event identity")
        if "episodeid" in query and query["episodeid"] != [episode]:
            raise NewsError("GDACS report URL does not match its episode")
        headline = _plain_text(item.findtext("title") or "", 500)
        if not headline:
            raise NewsError("GDACS bulletin requires a headline")
        published = _date(item.findtext("pubDate") or "", now=retrieved_at)
        start = (item.findtext(GDACS + "fromdate") or "").strip()
        end = (item.findtext(GDACS + "todate") or "").strip()
        alert = _plain_text(item.findtext(GDACS + "alertlevel") or "", 100) or None
        summary = ("GDACS published this hazard bulletin. Source alert levels describe modelled potential humanitarian impact; "
                   "they do not confirm damage or casualties. Source date windows may include forecasts.")
        article = NewsArticle(id=f"gdacs-report-{eventtype}-{eventid}", canonical_url=url, headline=headline,
                              publisher="GDACS", publisher_id="gdacs", source_id="gdacs", record_kind="official_report",
                              license_url="https://commission.europa.eu/legal-notice_en", published_at=published,
                              retrieved_at=retrieved_at, summary=summary, is_demo=False,
                              observations=[NewsObservation(provider_id="gdacs", provider_url="https://www.gdacs.org/xml/rss.xml", retrieved_at=retrieved_at)],
                              source_window_start=_date(start) if start else None,
                              source_window_end=_date(end) if end else None)
        location = None
        try:
            point = (item.findtext(GEORSS + "point") or "").split()
            lat, lon = [float(value) for value in point]
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            location = NewsLocation(lat=lat, lon=lon,
                                    label=_plain_text(item.findtext(GDACS + "country") or "GDACS source reference point", 300),
                                    precision="approximate_area", confidence="unknown", source_url=url,
                                    basis="GDACS source-supplied reference point. It is not an exact incident address, affected-area boundary, or impact radius.")
        except (ValueError, TypeError):
            pass  # Missing or invalid source geography stays unlocated; never substitute a country centroid.
        identity = f"{eventtype}:{eventid}"
        event = NewsEvent(id=f"gdacs-event-{eventtype}-{eventid}", title=headline, summary=summary,
                          category=HAZARDS[eventtype], status="reported", severity="unknown",
                          severity_basis="GDACS alert is a source model of potential humanitarian impact, not validated incident severity or confirmed harm.",
                          grouping_basis=f"GDACS source event {identity}; retained episode {episode}. Episodes are revisions of one bulletin, not independent coverage.",
                          location=location, scope="located" if location else "unlocated", is_demo=False,
                          articles=[article], source_event_id=identity, source_alert_level=alert)
        key = (published, int(episode), event.model_dump_json())
        if identity not in retained or key > retained[identity][0]:
            retained[identity] = (key, event)
    events = [entry[1] for entry in retained.values()]
    events.sort(key=lambda event: (-event.articles[0].published_at.timestamp(), event.id))
    return events[:30], len(items) - len(retained)
