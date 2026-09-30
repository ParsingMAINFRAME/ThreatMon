"""Source contracts for bounded, attributed Global Voices and GDACS RSS parsing."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from html import escape
from urllib.parse import parse_qs, urlsplit

import pytest

from app.news.feeds import parse_gdacs_feed, parse_globalvoices_feed


NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
PUBLISHED = NOW - timedelta(hours=2)
MAX_FEED_BYTES = 1024 * 1024
GV_LICENSE = "https://creativecommons.org/licenses/by/3.0/"
BODY_MARKER = "SOURCE_BODY_MUST_NOT_BE_REPUBLISHED"
IMAGE_MARKER = "source-image-must-not-be-retained.jpg"


def tag(name: str, value: str | None) -> str:
    return "" if value is None else f"<{name}>{escape(value)}</{name}>"


def rss(*items: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:media="http://search.yahoo.com/mrss/" '
        'xmlns:georss="http://www.georss.org/georss" '
        'xmlns:gdacs="http://www.gdacs.org">'
        f'<channel><title>Fixture feed</title>{"".join(items)}</channel></rss>'
    ).encode("utf-8")


def gv_item(
    *,
    link: str | None = "https://globalvoices.org/2026/09/30/example/",
    title: str = "Community reporting from a country",
    published: str | None = format_datetime(PUBLISHED),
    author: str | None = "Example Author",
    description: str = BODY_MARKER,
) -> str:
    return (
        "<item>"
        + tag("title", title)
        + tag("link", link)
        + tag("pubDate", published)
        + tag("dc:creator", author)
        + tag("description", f"<p>{description}</p>")
        + tag("content:encoded", f"<article>{BODY_MARKER}</article>")
        + f'<media:thumbnail url="https://globalvoices.org/{IMAGE_MARKER}"/>'
        + "</item>"
    )


def report_url(event_type: str = "EQ", event_id: str = "123", episode: str = "1") -> str:
    return f"https://www.gdacs.org/report.aspx?eventtype={event_type}&eventid={event_id}&episodeid={episode}"


def gdacs_item(
    *,
    event_type: str | None = "EQ",
    event_id: str | None = "123",
    episode: str | None = "1",
    link: str | None = None,
    title: str = "Source disaster bulletin",
    published: str | None = format_datetime(PUBLISHED),
    point: str | None = "-12.5 130.75",
    alert: str = "Orange",
    window_start: str | None = "Wed, 30 Sep 2026 09:00:00 GMT",
    window_end: str | None = "Thu, 01 Oct 2026 09:00:00 GMT",
    extra: str = "",
) -> str:
    if link is None:
        link = report_url(event_type or "EQ", event_id or "123", episode or "1")
    return (
        "<item>"
        + tag("title", title)
        + tag("link", link)
        + tag("pubDate", published)
        + tag("gdacs:eventtype", event_type)
        + tag("gdacs:eventid", event_id)
        + tag("gdacs:episodeid", episode)
        + tag("gdacs:alertlevel", alert)
        + tag("gdacs:country", "Example country")
        + tag("gdacs:fromdate", window_start)
        + tag("gdacs:todate", window_end)
        + tag("georss:point", point)
        + tag("description", f"<p>{BODY_MARKER}</p>")
        + tag("content:encoded", f"<article>{BODY_MARKER}</article>")
        + f'<enclosure url="https://www.gdacs.org/{IMAGE_MARKER}" type="image/jpeg"/>'
        + extra
        + "</item>"
    )


def test_globalvoices_preserves_attribution_without_republishing_content_or_inventing_incident():
    events, excluded = parse_globalvoices_feed(
        rss(gv_item(published="Wed, 30 Sep 2026 12:00:00 +0200")), retrieved_at=NOW,
    )
    assert len(events) == 1 and excluded == 0
    event = events[0]
    article = event.articles[0]
    assert not event.is_demo and not article.is_demo
    assert event.scope == "unlocated" and event.location is None
    assert event.status == "reported" and event.severity == "unknown"
    assert article.publisher == "Global Voices"
    assert article.source_id == article.publisher_id == "globalvoices"
    assert article.record_kind == "article"
    assert article.author == "Example Author" and article.license_url == GV_LICENSE
    assert article.published_at == PUBLISHED and article.published_at.tzinfo == UTC
    assert article.retrieved_at == NOW
    assert article.headline == "Community reporting from a country"
    assert article.summary and event.summary
    assert BODY_MARKER not in event.model_dump_json()
    assert IMAGE_MARKER not in event.model_dump_json()
    other, _ = parse_globalvoices_feed(rss(gv_item(description="An entirely different body")), retrieved_at=NOW)
    assert other[0].summary == event.summary
    assert other[0].articles[0].summary == article.summary


def test_globalvoices_deduplicates_canonical_links_before_applying_twenty_story_limit():
    items = [gv_item(link=f"https://globalvoices.org/story-{i}/") for i in range(25)]
    duplicates = [gv_item(link="https://globalvoices.org/story-0/?utm_source=feed#top") for _ in range(5)]
    events, excluded = parse_globalvoices_feed(rss(*duplicates, *items), retrieved_at=NOW)
    assert len(events) == 20 and excluded == 5
    articles = [event.articles[0] for event in events]
    assert len({article.id for article in articles}) == 20
    assert len({article.canonical_url for article in articles}) == 20
    assert all(len(event.articles) == 1 for event in events)


def test_globalvoices_same_headline_does_not_merge_different_publisher_urls():
    events, excluded = parse_globalvoices_feed(
        rss(gv_item(link="https://globalvoices.org/first/"), gv_item(link="https://globalvoices.org/second/")),
        retrieved_at=NOW,
    )
    assert len(events) == 2 and excluded == 0
    assert events[0].id != events[1].id


@pytest.mark.parametrize("host", ["globalvoices.org", "www.globalvoices.org"])
def test_globalvoices_accepts_only_documented_publisher_hosts_and_normalizes_tracking(host):
    events, _ = parse_globalvoices_feed(
        rss(gv_item(link=f"https://{host}/story/?utm_source=rss#section")), retrieved_at=NOW,
    )
    assert events[0].articles[0].canonical_url == f"https://{host}/story/"


@pytest.mark.parametrize("author", [None, "", "a" * 301])
def test_globalvoices_missing_or_truncated_author_credit_is_not_published(author):
    with pytest.raises(ValueError):
        parse_globalvoices_feed(rss(gv_item(author=author)), retrieved_at=NOW)


def test_globalvoices_preserves_complete_bounded_author_credit():
    author = "a" * 300
    events, _ = parse_globalvoices_feed(rss(gv_item(author=author)), retrieved_at=NOW)
    assert events[0].articles[0].author == author


def test_gdacs_preserves_publisher_alert_location_provenance_and_future_source_window():
    link = report_url() + "&utm_source=rss#map"
    events, excluded = parse_gdacs_feed(rss(gdacs_item(link=link)), retrieved_at=NOW)
    assert len(events) == 1 and excluded == 0
    event = events[0]
    article = event.articles[0]
    assert event.source_event_id == "EQ:123"
    assert event.source_alert_level == "Orange"
    assert event.status == "reported" and event.severity == "unknown"
    assert not event.is_demo and not article.is_demo
    assert article.source_id == article.publisher_id == "gdacs"
    assert article.record_kind == "official_report"
    assert article.published_at == PUBLISHED and article.retrieved_at == NOW
    assert article.source_window_start == datetime(2026, 9, 30, 9, tzinfo=UTC)
    assert article.source_window_end == datetime(2026, 10, 1, 9, tzinfo=UTC)
    assert article.source_window_end > article.retrieved_at
    assert event.scope == "located" and event.location is not None
    assert event.location.lat == -12.5 and event.location.lon == 130.75
    assert event.location.precision == "approximate_area" and event.location.confidence == "unknown"
    assert event.location.basis and event.location.source_url == article.canonical_url
    assert parse_qs(urlsplit(article.canonical_url).query) == {
        "eventtype": ["EQ"], "eventid": ["123"], "episodeid": ["1"],
    }
    assert not urlsplit(article.canonical_url).fragment
    assert BODY_MARKER not in event.model_dump_json()
    assert IMAGE_MARKER not in event.model_dump_json()


@pytest.mark.parametrize("alert", ["Green", "Orange", "Red"])
def test_gdacs_source_alert_never_becomes_app_severity_or_lifecycle(alert):
    events, _ = parse_gdacs_feed(rss(gdacs_item(alert=alert)), retrieved_at=NOW)
    assert events[0].source_alert_level == alert
    assert events[0].severity == "unknown" and events[0].status == "reported"


@pytest.mark.parametrize("event_type", ["EQ", "FL", "TC", "DR", "WF", "VO"])
def test_gdacs_supported_hazards_retain_type_qualified_source_identity(event_type):
    events, _ = parse_gdacs_feed(rss(gdacs_item(event_type=event_type)), retrieved_at=NOW)
    assert events[0].source_event_id == f"{event_type}:123"


def test_gdacs_event_and_article_identity_survive_episode_revisions():
    first, _ = parse_gdacs_feed(rss(gdacs_item(episode="1")), retrieved_at=NOW)
    revised, _ = parse_gdacs_feed(
        rss(gdacs_item(episode="2", title="Revised bulletin", published=format_datetime(PUBLISHED + timedelta(hours=1)))),
        retrieved_at=NOW,
    )
    assert first[0].id == revised[0].id
    assert first[0].articles[0].id == revised[0].articles[0].id
    assert first[0].source_event_id == revised[0].source_event_id == "EQ:123"
    assert first[0].articles[0].canonical_url != revised[0].articles[0].canonical_url


def test_gdacs_event_identity_deduplicates_revisions_without_claiming_syndication():
    events, excluded = parse_gdacs_feed(
        rss(gdacs_item(episode="1"), gdacs_item(episode="2")), retrieved_at=NOW,
    )
    assert len(events) == 1 and excluded == 1
    assert events[0].source_event_id == "EQ:123"
    assert len(events[0].articles) == 1
    article = events[0].articles[0]
    assert article.record_kind == "official_report" and article.publisher_id == "gdacs"
    assert article.syndication_key is None


def test_gdacs_retains_latest_publication_then_highest_numeric_episode_independent_of_feed_order():
    items = [
        gdacs_item(episode="99", published=format_datetime(PUBLISHED - timedelta(hours=1))),
        gdacs_item(episode="9", title="Episode nine"),
        gdacs_item(episode="12", title="Episode twelve"),
    ]
    events, excluded = parse_gdacs_feed(rss(*items), retrieved_at=NOW)
    reversed_events, reversed_excluded = parse_gdacs_feed(rss(*reversed(items)), retrieved_at=NOW)
    assert excluded == reversed_excluded == 2 and len(events) == 1
    assert events[0].articles[0].headline == "Episode twelve"
    assert events[0].articles[0].published_at == PUBLISHED
    assert [event.model_dump() for event in events] == [event.model_dump() for event in reversed_events]


def test_gdacs_equal_publication_and_episode_have_deterministic_tie_resolution():
    items = [gdacs_item(title="Alpha bulletin"), gdacs_item(title="Beta bulletin")]
    first, excluded = parse_gdacs_feed(rss(*items), retrieved_at=NOW)
    second, other_excluded = parse_gdacs_feed(rss(*reversed(items)), retrieved_at=NOW)
    assert excluded == other_excluded == 1
    assert [event.model_dump() for event in first] == [event.model_dump() for event in second]


def test_gdacs_same_numeric_id_for_different_hazards_is_not_a_duplicate():
    events, excluded = parse_gdacs_feed(rss(gdacs_item(event_type="EQ"), gdacs_item(event_type="FL")), retrieved_at=NOW)
    assert len(events) == 2 and excluded == 0
    assert {event.source_event_id for event in events} == {"EQ:123", "FL:123"}
    assert len({event.id for event in events}) == len({event.articles[0].id for event in events}) == 2


def test_gdacs_deduplicates_before_thirty_event_limit_and_returns_latest_publications_first():
    items = [
        gdacs_item(event_id=str(i), published=format_datetime(PUBLISHED - timedelta(minutes=i)))
        for i in range(1, 36)
    ]
    duplicates = [gdacs_item(event_id="1", episode=str(i + 2), published=format_datetime(PUBLISHED - timedelta(minutes=1))) for i in range(5)]
    events, excluded = parse_gdacs_feed(rss(*reversed(items), *duplicates), retrieved_at=NOW)
    assert len(events) == 30 and excluded == 5
    assert [event.source_event_id for event in events] == [f"EQ:{i}" for i in range(1, 31)]
    dates = [event.articles[0].published_at for event in events]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.parametrize("point", [None, "", "91 0", "0 181", "nan 0", "0 inf", "-inf 0", "1", "1 2 3", "1,2", "north east"])
def test_gdacs_missing_or_invalid_source_coordinates_leave_the_report_unlocated(point):
    events, _ = parse_gdacs_feed(rss(gdacs_item(point=point)), retrieved_at=NOW)
    assert len(events) == 1 and events[0].location is None and events[0].scope == "unlocated"
    assert events[0].source_event_id == "EQ:123" and events[0].status == "reported"


def test_gdacs_does_not_infer_coordinates_from_names_or_other_xml_fields():
    extra = '<latitude>-12.5</latitude><longitude>130.75</longitude><point>-12.5 130.75</point>'
    events, _ = parse_gdacs_feed(rss(gdacs_item(point=None, extra=extra, title="Earthquake near Tokyo, Japan")), retrieved_at=NOW)
    assert events[0].location is None and events[0].scope == "unlocated"


def test_gdacs_zero_coordinates_are_valid_source_coordinates():
    events, _ = parse_gdacs_feed(rss(gdacs_item(point="0 0")), retrieved_at=NOW)
    assert events[0].scope == "located"
    assert events[0].location.lat == events[0].location.lon == 0


def test_gdacs_absent_optional_source_windows_remain_unknown():
    events, _ = parse_gdacs_feed(rss(gdacs_item(window_start=None, window_end=None)), retrieved_at=NOW)
    assert events[0].articles[0].source_window_start is None
    assert events[0].articles[0].source_window_end is None


@pytest.mark.parametrize("window", [
    {"window_start": "not-a-date"},
    {"window_end": "Wed, 30 Sep 2026 09:00:00"},
])
def test_gdacs_malformed_or_timezone_free_source_windows_fail_the_source(window):
    with pytest.raises(ValueError):
        parse_gdacs_feed(rss(gdacs_item(**window)), retrieved_at=NOW)


@pytest.mark.parametrize("fields", [
    {"event_type": None}, {"event_id": None}, {"event_id": ""}, {"event_type": "UNKNOWN"},
    {"event_id": "not-a-number"}, {"published": None}, {"published": "not-a-date"},
    {"published": "Wed, 30 Sep 2026 10:00:00"},
    {"published": "Thu, 01 Oct 2026 10:00:00 GMT"},
])
def test_gdacs_invalid_required_identity_or_publication_fails_source(fields):
    with pytest.raises(ValueError):
        parse_gdacs_feed(rss(gdacs_item(**fields)), retrieved_at=NOW)


def test_gdacs_missing_report_link_fails_source():
    item = gdacs_item().replace(tag("link", report_url()), "")
    with pytest.raises(ValueError):
        parse_gdacs_feed(rss(item), retrieved_at=NOW)


@pytest.mark.parametrize("fields", [
    {"link": None}, {"link": ""}, {"published": None}, {"published": "not-a-date"},
    {"published": "Wed, 30 Sep 2026 10:00:00"},
    {"published": "Thu, 01 Oct 2026 10:00:00 GMT"},
])
def test_globalvoices_missing_link_or_invalid_publication_fails_source(fields):
    with pytest.raises(ValueError):
        parse_globalvoices_feed(rss(gv_item(**fields)), retrieved_at=NOW)


@pytest.mark.parametrize("url", [
    "http://globalvoices.org/story/", "https://fr.globalvoices.org/story/",
    "https://globalvoices.org.evil.example/story/", "https://example.org/story/",
    "https://user:password@globalvoices.org/story/", "https://globalvoices.org:444/story/",
    "https://127.0.0.1/story/", "javascript:alert(1)", "//globalvoices.org/story/",
])
def test_globalvoices_unsafe_or_unapproved_publisher_urls_fail_source(url):
    with pytest.raises(ValueError):
        parse_globalvoices_feed(rss(gv_item(link=url)), retrieved_at=NOW)


@pytest.mark.parametrize("url", [
    "http://www.gdacs.org/report.aspx?eventtype=EQ&eventid=123",
    "https://api.gdacs.org/report.aspx?eventtype=EQ&eventid=123",
    "https://www.gdacs.org.evil.example/report.aspx?eventtype=EQ&eventid=123",
    "https://user:password@www.gdacs.org/report.aspx?eventtype=EQ&eventid=123",
    "https://www.gdacs.org:444/report.aspx?eventtype=EQ&eventid=123",
    "https://127.0.0.1/report.aspx?eventtype=EQ&eventid=123",
    "javascript:alert(1)", "//www.gdacs.org/report.aspx?eventtype=EQ&eventid=123",
    "https://www.gdacs.org/other.aspx?eventtype=EQ&eventid=123",
    "https://www.gdacs.org/report.aspx?eventtype=FL&eventid=123",
    "https://www.gdacs.org/report.aspx?eventtype=EQ&eventid=999",
    "https://www.gdacs.org/report.aspx?eventtype=EQ",
    "https://www.gdacs.org/report.aspx?eventid=123",
    "https://www.gdacs.org/report.aspx?eventtype=EQ&eventtype=FL&eventid=123",
    "https://www.gdacs.org/report.aspx?eventtype=EQ&eventid=123&eventid=999",
])
def test_gdacs_unsafe_or_identity_mismatched_report_urls_fail_source(url):
    with pytest.raises(ValueError):
        parse_gdacs_feed(rss(gdacs_item(link=url)), retrieved_at=NOW)


@pytest.mark.parametrize("host", ["gdacs.org", "www.gdacs.org"])
def test_gdacs_accepts_documented_report_hosts(host):
    events, _ = parse_gdacs_feed(rss(gdacs_item(link=report_url().replace("www.gdacs.org", host))), retrieved_at=NOW)
    assert urlsplit(events[0].articles[0].canonical_url).hostname == host


PARSERS = [parse_globalvoices_feed, parse_gdacs_feed]


@pytest.mark.parametrize("parser", PARSERS, ids=["globalvoices", "gdacs"])
@pytest.mark.parametrize("payload", [b"<rss><channel><item></rss>", b"<html>Forbidden</html>", rss()])
def test_invalid_or_empty_feed_is_a_source_failure(parser, payload):
    with pytest.raises(ValueError):
        parser(payload, retrieved_at=NOW)


@pytest.mark.parametrize("parser", PARSERS, ids=["globalvoices", "gdacs"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_xml_document_types_and_entities_are_rejected_in_every_encoding(parser, encoding):
    xml = '<!DOCTYPE rss [<!ENTITY x "unsafe-entity">]><rss><channel><title>&x;</title></channel></rss>'
    with pytest.raises(ValueError):
        parser(xml.encode(encoding), retrieved_at=NOW)


@pytest.mark.parametrize("parser,item", [(parse_globalvoices_feed, gv_item), (parse_gdacs_feed, gdacs_item)], ids=["globalvoices", "gdacs"])
@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_non_utf8_feed_cannot_bypass_xml_validation(parser, item, encoding):
    with pytest.raises(ValueError):
        parser(rss(item()).decode("utf-8").encode(encoding), retrieved_at=NOW)


@pytest.mark.parametrize("parser,item", [(parse_globalvoices_feed, gv_item), (parse_gdacs_feed, gdacs_item)], ids=["globalvoices", "gdacs"])
def test_feed_size_limit_is_one_mib_including_valid_xml_padding(parser, item):
    body = rss(item())
    at_limit = body + b" " * (MAX_FEED_BYTES - len(body))
    events, _ = parser(at_limit, retrieved_at=NOW)
    assert len(events) == 1
    with pytest.raises(ValueError):
        parser(at_limit + b" ", retrieved_at=NOW)


@pytest.mark.parametrize("parser,item", [(parse_globalvoices_feed, gv_item), (parse_gdacs_feed, gdacs_item)], ids=["globalvoices", "gdacs"])
def test_one_invalid_item_does_not_silently_turn_a_broken_source_into_success(parser, item):
    with pytest.raises(ValueError):
        parser(rss(item(), item(published="invalid")), retrieved_at=NOW)
