"""Wikipedia Current events portal: curated one-sentence event entries with cited source links.

Entry text is written by Wikipedia contributors (CC BY-SA 4.0), not by the linked
publisher. Each entry is kept as discovery metadata for its first cited source
URL. The portal day is an event-day label chosen by editors, not a publication time.
"""

from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from urllib.parse import quote, urlsplit

from app.news.models import NewsArticle, NewsEvent, NewsObservation
from app.news.service import MAX_FEED_BYTES, NewsError, _plain_text
from app.news.urls import canonical_url

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/"
PAGE_PREFIX = "Portal:Current events/"
DAYS = 3
MAX_ENTRIES = 120
# Sections that describe incidents; arts, business, science and sport are not collected.
SECTIONS = {"armed conflicts and attacks", "disasters and accidents", "law and crime", "politics and elections",
            "health and environment", "international relations"}
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")


def page_title(day: datetime) -> str:
    return f"{PAGE_PREFIX}{day.year} {MONTH_NAMES[day.month - 1]} {day.day}"


def request_url(now: datetime) -> str:
    """One bounded request for today's and the two previous UTC days' pages."""
    titles = "|".join(page_title(now - timedelta(days=offset)) for offset in range(DAYS))
    return (f"{WIKIPEDIA_API_URL}?action=query&prop=revisions&rvprop=content&rvslots=main&format=json&formatversion=2"
            f"&titles={quote(titles, safe='')}")


def _page_day(title: str) -> datetime:
    match = re.fullmatch(re.escape(PAGE_PREFIX) + r"(\d{4}) ([A-Z][a-z]+) (\d{1,2})", title)
    if not match or match[2] not in MONTH_NAMES:
        raise ValueError("Unexpected Current events page title")
    return datetime(int(match[1]), MONTH_NAMES.index(match[2]) + 1, int(match[3]), tzinfo=UTC)


def _sentence(wikitext: str) -> str:
    text = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", " ", wikitext, flags=re.DOTALL)
    text = re.sub(r"\[https?://[^\]]*\]", " ", text)  # cited source links
    text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    text = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    return _plain_text(text, 500).strip()


def link_titles(wikitext: str) -> list[str]:
    """Target article titles of the internal links in one line, in order, without duplicates or other namespaces."""
    titles: list[str] = []
    for target in re.findall(r"\[\[([^\[\]|]+)(?:\|[^\[\]]*)?\]\]", wikitext):
        title = target.split("#")[0].replace("_", " ").strip()
        if not title or ":" in title:
            continue  # Files, categories and other namespaces are not article links.
        title = title[0].upper() + title[1:]
        if title not in titles and len(title) <= 300:
            titles.append(title)
    return titles


def parse_current_events(body: bytes, *, retrieved_at: datetime) -> tuple[list[NewsEvent], int]:
    if len(body) > MAX_FEED_BYTES:
        raise NewsError("Wikipedia response exceeds the 1 MiB limit")
    try:
        data = json.loads(body.decode("utf-8-sig"))
        pages = data["query"]["pages"]
        if not isinstance(pages, list) or len(pages) > DAYS:
            raise ValueError
        entries: dict[str, NewsArticle] = {}
        excluded = 0
        for page in sorted(pages, key=lambda item: _page_day(item["title"]), reverse=True):
            day = _page_day(page["title"])
            if day > retrieved_at:
                raise ValueError("Current events page is dated in the future")
            if page.get("missing"):
                continue  # Today's page may not exist yet.
            wikitext = page["revisions"][0]["slots"]["main"]["content"]
            if not isinstance(wikitext, str):
                raise ValueError
            page_url = "https://en.wikipedia.org/wiki/" + quote(page["title"].replace(" ", "_"), safe=":/")
            section = None
            topics: list[tuple[int, str]] = []  # (bullet depth, heading) for the bullets above the current line
            for line in wikitext.splitlines():
                heading = re.fullmatch(r"\s*'''([^']+)'''\s*", line)
                if heading:
                    section = heading[1].strip().casefold()
                    topics = []
                    continue
                depth = len(line) - len(line.lstrip("*"))
                if depth:
                    topics = [topic for topic in topics if topic[0] < depth]
                links = re.findall(r"\[(https://[^\s\]]+)(?:\s+([^\]]*))?\]", line)
                if depth and not links:
                    # A bullet without a cited source is a topic heading, such as "[[Gaza war]]", for the entries nested under it.
                    topic = (link_titles(line) or [_sentence(line.lstrip("* "))])[0]
                    if topic:
                        topics.append((depth, topic[:300]))
                    continue
                if section not in SECTIONS or not depth or not links:
                    continue
                headline = _sentence(line.lstrip("* "))
                try:
                    url = canonical_url(links[0][0])
                except ValueError:
                    continue  # An unsafe cited link is dropped with its entry.
                host = (urlsplit(url).hostname or "").removeprefix("www.")
                if not headline or not host:
                    continue
                if url in entries:
                    excluded += 1
                    continue
                if len(entries) >= MAX_ENTRIES:
                    break
                publisher = _plain_text(links[0][1].replace("''", "").strip("() "), 200) or host
                entries[url] = NewsArticle(
                    id=f"wikipedia-article-{hashlib.sha256(url.encode()).hexdigest()[:24]}", canonical_url=url,
                    headline=headline, publisher=publisher, publisher_id=host, source_id="wikipedia",
                    author="Wikipedia contributors", license_url=WIKIPEDIA_LICENSE,
                    published_at=None, first_seen_at=retrieved_at, retrieved_at=retrieved_at,
                    source_window_start=day, source_window_end=min(day + timedelta(days=1), retrieved_at),
                    editor_section=section, editor_topics=[topic for _, topic in topics][-4:],
                    linked_titles=link_titles(re.sub(r"<ref[^>]*>.*?</ref>", " ", line, flags=re.DOTALL))[:32],
                    observations=[NewsObservation(provider_id="wikipedia", provider_url=page_url, provider_timestamp=day,
                                                  provider_timestamp_raw=page["title"].removeprefix(PAGE_PREFIX),
                                                  retrieved_at=retrieved_at, language="English")],
                    summary=(f"Entry text from Wikipedia's Current events portal ({page_url}), written by Wikipedia contributors under CC BY-SA 4.0, "
                             f"not by {publisher}. The link opens the first source the entry cites. The portal day is an editor-chosen event day, not a publication time."),
                    is_demo=False)
        events = [NewsEvent(id=article.id.replace("-article-", "-event-"), title=article.headline, summary=article.summary,
                            category="world_news", status="reported", severity="unknown",
                            severity_basis="A curated portal entry does not verify an incident or establish severity.",
                            grouping_basis="One Wikipedia Current events entry and its first cited source; no inferred grouping or corroboration.",
                            grouping_status="single_source", location=None, scope="unlocated", is_demo=False, articles=[article])
                  for article in entries.values()]
        return events, excluded
    except (KeyError, IndexError, ValueError, TypeError, UnicodeError) as error:
        if isinstance(error, NewsError):
            raise
        raise NewsError("Wikipedia returned an unexpected Current events response") from error
