"""GDELT 2.0 Global Knowledge Graph 15-minute files as article discovery metadata.

GDELT asks high-traffic and rate-limited users to read its published bulk files
instead of the DOC search API. Each file lists the articles GDELT monitored in
one 15-minute window. Only the page title, URL, publisher domain and file time
are kept, and only for titles the headline rules can place. GDELT's own location
list is used as a check on that placement, never as a coordinate.
"""

from datetime import UTC, datetime, timedelta
import hashlib
import html
import io
import re
from urllib.parse import urlsplit
import zipfile

from app.news.grouping import placed_country
from app.news.models import NewsArticle, NewsObservation
from app.news.service import NewsError, _plain_text
from app.news.urls import canonical_url

LASTUPDATE_URL = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
FILE_URL = "https://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip"
BULK_QUERY = "GKG 15-minute files; incident headlines naming one clear place"
FILE_INTERVAL = timedelta(minutes=15)
MAX_FILES_PER_IMPORT = 4
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_CSV_BYTES = 96 * 1024 * 1024
GKG_COLUMNS = 27
# GDELT location names for places our gazetteer labels differently.
COUNTRY_NAMES = {
    "Palestine": ("gaza", "west bank", "israel", "palestin"), "Congo": ("congo",), "Myanmar": ("myanmar", "burma"),
    "Czech Republic": ("czech",), "South Korea": ("korea",), "North Korea": ("korea",),
}


def latest_file_time(body: bytes) -> datetime:
    """Read the newest file time from lastupdate.txt without trusting any URL in it."""
    match = re.search(rb"/gdeltv2/(\d{14})\.gkg\.csv\.zip\s*$", body[:2000], re.MULTILINE)
    if not match:
        raise NewsError("GDELT lastupdate.txt did not list a GKG file")
    try:
        return datetime.strptime(match[1].decode(), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError as error:
        raise NewsError("GDELT lastupdate.txt listed an invalid file time") from error


def file_times(latest: datetime, watermark: datetime | None) -> tuple[list[datetime], bool]:
    """Newest files not yet read, oldest first, and whether older unread files were skipped."""
    times = []
    current = latest
    while len(times) < MAX_FILES_PER_IMPORT and (watermark is None or current > watermark):
        times.append(current)
        current -= FILE_INTERVAL
    skipped = watermark is not None and current > watermark
    return list(reversed(times)), skipped


def file_url(time: datetime) -> str:
    return FILE_URL.format(stamp=time.strftime("%Y%m%d%H%M%S"))


def _corroborated(country: str, locations: str) -> bool:
    """GDELT's location list must name our country at least as often as any other country.

    An article about Athens, Alabama lists mostly United States places even when GDELT also
    geocodes one mention to Greece, so a plurality check rejects that same-name mistake.
    """
    wanted = COUNTRY_NAMES.get(country, (country.casefold(),))
    counts: dict[str, int] = {}
    for entry in locations.split(";"):
        fields = entry.split("#")
        if len(fields) > 1 and fields[1].strip():
            place_country = fields[1].rsplit(",", 1)[-1].strip().casefold()
            key = "*" if any(name in place_country for name in wanted) else place_country
            counts[key] = counts.get(key, 0) + 1
    return counts.get("*", 0) > 0 and counts["*"] == max(counts.values())


def parse_gkg_file(body: bytes, *, file_time: datetime, retrieved_at: datetime) -> list[NewsArticle]:
    if len(body) > MAX_ZIP_BYTES:
        raise NewsError("GDELT file exceeds the 16 MiB download limit")
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].file_size > MAX_CSV_BYTES:
                raise NewsError("GDELT file has an unexpected archive layout or size")
            text = archive.read(members[0]).decode("utf-8", "replace")
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        if isinstance(error, NewsError):
            raise
        raise NewsError("GDELT file is not a readable zip archive") from error
    provider_url = file_url(file_time)
    articles: dict[str, NewsArticle] = {}
    for line in text.split("\n"):
        columns = line.split("\t")
        if len(columns) != GKG_COLUMNS:
            continue
        title = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", columns[26])
        headline = _plain_text(html.unescape(title[1]), 500) if title else ""
        if not headline:
            continue
        try:
            url = canonical_url(columns[4])
        except ValueError:
            continue  # GKG also lists non-web documents; an unusable link drops only its own record.
        publisher = (urlsplit(url).hostname or "").removeprefix("www.")
        if not publisher or url in articles:
            continue
        article = NewsArticle(
            id=f"article-{hashlib.sha256(url.encode()).hexdigest()[:24]}", canonical_url=url, headline=headline,
            publisher=publisher, publisher_id=publisher, source_id="gdelt", published_at=None,
            first_seen_at=retrieved_at, retrieved_at=retrieved_at, is_demo=False,
            observations=[NewsObservation(provider_id="gdelt", provider_url=provider_url, provider_timestamp=file_time,
                                          provider_timestamp_raw=file_time.strftime("%Y%m%d%H%M%S"),
                                          retrieved_at=retrieved_at, language="English")],
            summary="GDELT listed this publisher article in a 15-minute monitoring file. The file time is when GDELT saw it, not a publication date; consult the original source for context.")
        country = placed_country(article)
        # Keep only headlines the map can place, and only when GDELT's own reading of the article names the same country.
        if country is not None and _corroborated(country, columns[9]):
            articles[url] = article
    return list(articles.values())
