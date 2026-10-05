"""GDELT provider timestamps must not imply publication dates or incident locations."""

from datetime import UTC, datetime, timedelta
import json

import pytest

from app.news.gdelt import parse_gdelt_response


NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
SEEN = datetime(2026, 9, 30, 10, tzinfo=UTC)
PROVIDER_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_RESPONSE_BYTES = 1024 * 1024


def record(**changes):
    value = {
        "url": "https://www.publisher.example/news/story?id=123",
        "title": "A publisher reports developments",
        "seendate": "20260930T100000Z",
        "domain": "untrusted-domain.example",
        "language": "English",
        "sourcecountry": "France",
    }
    value.update(changes)
    return value


def response(*records):
    return json.dumps({"articles": list(records)}, ensure_ascii=False).encode("utf-8")


def test_gdelt_preserves_provider_provenance_without_inventing_publication_or_incident():
    events, excluded = parse_gdelt_response(response(record()), retrieved_at=NOW)
    assert len(events) == 1 and excluded == 0
    event = events[0]
    assert len(event.articles) == 1
    article = event.articles[0]
    assert article.canonical_url == "https://www.publisher.example/news/story?id=123"
    assert article.publisher == article.publisher_id == "publisher.example"
    assert article.source_id == "gdelt" and article.record_kind == "article"
    assert article.headline == "A publisher reports developments"
    assert article.author is None and article.license_url is None
    assert article.published_at is None
    assert article.first_seen_at == NOW and article.first_seen_at.tzinfo == UTC
    assert article.retrieved_at == NOW
    assert [item.model_dump() for item in article.observations] == [{
        "provider_id": "gdelt",
        "provider_url": PROVIDER_URL,
        "provider_timestamp": SEEN,
        "provider_timestamp_raw": "20260930T100000Z",
        "retrieved_at": NOW,
        "language": "English",
        "source_country": "France",
    }]
    assert event.location is None and event.scope == "unlocated"
    assert event.severity == "unknown" and event.status == "reported"
    assert event.source_event_id is None and event.source_alert_level is None
    assert not event.is_demo and not article.is_demo


@pytest.mark.parametrize("url,publisher", [
    ("https://WWW.PUBLISHER.EXAMPLE/story", "publisher.example"),
    ("https://publisher.example/story", "publisher.example"),
    ("https://news.publisher.example/story", "news.publisher.example"),
    ("http://publisher.example/story", "publisher.example"),
])
def test_gdelt_publisher_identity_comes_only_from_the_canonical_article_hostname(url, publisher):
    events, _ = parse_gdelt_response(
        response(record(url=url, domain="GDELT", sourcecountry="publisher-country-is-not-the-publisher")),
        retrieved_at=NOW,
    )
    article = events[0].articles[0]
    assert article.publisher == article.publisher_id == publisher
    assert article.source_id == "gdelt"
    assert events[0].scope == "unlocated" and events[0].location is None


def test_gdelt_identities_survive_tracking_headline_and_provider_timestamp_changes():
    first, _ = parse_gdelt_response(response(record()), retrieved_at=NOW)
    later, _ = parse_gdelt_response(response(record(
        url="https://www.publisher.example/news/story?utm_source=gdelt&id=123&fbclid=tracking#section",
        title="A revised publisher headline",
        seendate="20260930T110000Z",
    )), retrieved_at=NOW + timedelta(hours=1))
    assert first[0].id == later[0].id
    assert first[0].articles[0].id == later[0].articles[0].id
    assert first[0].articles[0].canonical_url == later[0].articles[0].canonical_url
    assert first[0].articles[0].first_seen_at != later[0].articles[0].first_seen_at


def test_gdelt_canonical_url_dedup_merges_observations_instead_of_inflating_article_volume():
    items = [
        record(),
        record(url="https://www.publisher.example/news/story?utm_source=feed&id=123#top"),
        record(
            url="https://www.publisher.example/news/story?id=123&gclid=tracking",
            seendate="20260930T110000Z", language="French", sourcecountry="Belgium",
        ),
    ]
    events, excluded = parse_gdelt_response(response(*items), retrieved_at=NOW)
    reversed_events, reversed_excluded = parse_gdelt_response(response(*reversed(items)), retrieved_at=NOW)
    assert excluded == reversed_excluded == 2 and len(events) == 1
    article = events[0].articles[0]
    assert len(events[0].articles) == 1 and article.first_seen_at == NOW
    assert len(article.observations) == 2
    assert {(item.provider_timestamp, item.language, item.source_country) for item in article.observations} == {
        (SEEN, "English", "France"),
        (SEEN + timedelta(hours=1), "French", "Belgium"),
    }
    assert all(item.provider_id == "gdelt" and item.provider_url == PROVIDER_URL for item in article.observations)
    assert [event.model_dump() for event in events] == [event.model_dump() for event in reversed_events]


def test_gdelt_semantic_query_identifiers_and_distinct_urls_remain_distinct_articles():
    events, excluded = parse_gdelt_response(response(
        record(url="https://publisher.example/story?id=1&utm_source=feed#one"),
        record(url="https://publisher.example/story?id=2&utm_source=feed#two"),
        record(url="https://other.example/story?id=1"),
    ), retrieved_at=NOW)
    assert len(events) == 3 and excluded == 0
    assert len({event.id for event in events}) == 3
    articles = [event.articles[0] for event in events]
    assert len({article.id for article in articles}) == 3
    assert {article.canonical_url for article in articles} == {
        "https://publisher.example/story?id=1", "https://publisher.example/story?id=2",
        "https://other.example/story?id=1",
    }
    assert len({article.headline for article in articles}) == 1


def test_gdelt_observations_with_shared_provider_timestamp_preserve_distinct_language_and_country():
    events, excluded = parse_gdelt_response(response(
        record(), record(language="French"), record(sourcecountry="Belgium"),
    ), retrieved_at=NOW)
    assert len(events) == 1 and excluded == 2
    observations = events[0].articles[0].observations
    assert len(observations) == 3
    assert {(item.language, item.source_country) for item in observations} == {
        ("English", "France"), ("French", "France"), ("English", "Belgium"),
    }


def test_gdelt_observation_limit_never_turns_provider_time_into_first_threatmon_collection():
    earliest = SEEN - timedelta(hours=1)
    items = [record(seendate=(earliest + timedelta(minutes=index)).strftime("%Y%m%dT%H%M%SZ")) for index in range(40)]
    events, excluded = parse_gdelt_response(response(*items), retrieved_at=NOW)
    assert len(events) == 1 and excluded == 39
    article = events[0].articles[0]
    assert len(article.observations) == 32
    assert article.first_seen_at == NOW and article.published_at is None


def test_gdelt_ignores_bodies_images_and_unsourced_metadata_without_inferring_coordinates():
    body_marker = "ARTICLE_BODY_MUST_NOT_BE_RETAINED"
    image_marker = "publisher-image-must-not-be-retained.jpg"
    events, _ = parse_gdelt_response(response(record(
        title="Reporting about Tokyo and surrounding areas",
        sourcecountry="Japan",
        description=body_marker, body=body_marker, content=body_marker,
        socialimage=f"https://publisher.example/{image_marker}",
        image=f"https://publisher.example/{image_marker}",
        author="UNSUPPORTED_AUTHOR_MUST_NOT_BE_INVENTED",
        license_url="https://example.org/UNSUPPORTED_LICENSE",
        published_at="2026-09-30T08:00:00Z",
        latitude=35.6762, longitude=139.6503, **{"georss:point": "35.6762 139.6503"},
    )), retrieved_at=NOW)
    event = events[0]
    article = event.articles[0]
    assert event.location is None and event.scope == "unlocated"
    assert article.published_at is None and article.author is None and article.license_url is None
    assert article.observations[0].source_country == "Japan"
    stored = event.model_dump_json()
    for marker in [body_marker, image_marker, "UNSUPPORTED_AUTHOR", "UNSUPPORTED_LICENSE", "35.6762", "139.6503"]:
        assert marker not in stored
    other, _ = parse_gdelt_response(response(record(
        title="Reporting about Tokyo and surrounding areas", sourcecountry="Japan",
    )), retrieved_at=NOW)
    assert event.summary == other[0].summary
    assert article.summary == other[0].articles[0].summary


def test_gdelt_empty_articles_is_a_successful_empty_observation():
    events, excluded = parse_gdelt_response(response(), retrieved_at=NOW)
    assert events == [] and excluded == 0


def test_gdelt_plain_text_message_is_reported_to_the_operator_not_parsed():
    with pytest.raises(ValueError, match="message instead of article metadata: Your query was too short"):
        parse_gdelt_response(b"Your query was too short or too long.\n", retrieved_at=NOW)
    with pytest.raises(ValueError, match="empty response"):
        parse_gdelt_response(b"", retrieved_at=NOW)

def test_gdelt_accepts_up_to_250_input_records():
    items = [record(url=f"https://publisher.example/story/{index}") for index in range(250)]
    events, excluded = parse_gdelt_response(response(*items), retrieved_at=NOW)
    assert len(events) == 250 and excluded == 0
    assert len({event.id for event in events}) == 250


@pytest.mark.parametrize("duplicates", [False, True], ids=["distinct", "duplicates"])
def test_gdelt_rejects_more_than_250_input_records_before_deduplication(duplicates):
    items = [record(url=f"https://publisher.example/story/{0 if duplicates else index}") for index in range(251)]
    with pytest.raises(ValueError):
        parse_gdelt_response(response(*items), retrieved_at=NOW)


def test_gdelt_one_mib_limit_counts_the_entire_json_response():
    body = response(record())
    at_limit = body + b" " * (MAX_RESPONSE_BYTES - len(body))
    events, excluded = parse_gdelt_response(at_limit, retrieved_at=NOW)
    assert len(events) == 1 and excluded == 0
    with pytest.raises(ValueError):
        parse_gdelt_response(at_limit + b" ", retrieved_at=NOW)


@pytest.mark.parametrize("payload", [
    b"", b"<html>Rate limited</html>", b'{"articles":', b'{"articles":[]} trailing',
    b"null", b"[]", b'"articles"', b"{}", b'{"articles":null}',
    b'{"articles":{}}', b'{"articles":"none"}', b'{"articles":[null]}',
    b'{"articles":[[]]}', b'{"articles":["story"]}', b'{"articles":[1]}',
    b'{"articles":[{}]}', b'{"articles":[],"unexpected":NaN}',
    b'{"articles":[],"unexpected":Infinity}', b'{"articles":[],"unexpected":-Infinity}',
])
def test_gdelt_malformed_json_or_unrecognized_response_shape_fails_source(payload):
    with pytest.raises(ValueError):
        parse_gdelt_response(payload, retrieved_at=NOW)


@pytest.mark.parametrize("missing", ["url", "title", "seendate"])
def test_gdelt_missing_required_article_metadata_fails_source(missing):
    item = record()
    del item[missing]
    with pytest.raises(ValueError):
        parse_gdelt_response(response(item), retrieved_at=NOW)


@pytest.mark.parametrize("field", ["url", "title", "seendate"])
@pytest.mark.parametrize("value", [None, "", 123, True, [], {}])
def test_gdelt_required_metadata_must_be_nonempty_strings(field, value):
    with pytest.raises(ValueError):
        parse_gdelt_response(response(record(**{field: value})), retrieved_at=NOW)


@pytest.mark.parametrize("date", [
    "20261001T100000Z",  # A future provider timestamp fails source validation.
    "20260930T100000",  # Missing timezone is not UTC evidence.
    "2026-09-30 10:00:00", "2026-09-30T10:00:00Z", "Wed, 30 Sep 2026 10:00:00 GMT",
    "20261330T100000Z", "20260230T100000Z", "20260930T250000Z", "not-a-date",
])
def test_gdelt_invalid_future_or_naive_provider_time_fails_without_inventing_publication(date):
    with pytest.raises(ValueError):
        parse_gdelt_response(response(record(seendate=date)), retrieved_at=NOW)


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "data:text/html,unsafe", "file:///etc/passwd",
    "//publisher.example/story", "https://user:password@publisher.example/story",
    "https://publisher.example:444/story", "https://127.0.0.1/story",
    "http://[::1]/story", "http://localhost/story", "https://host.internal/story",
    "https://publisher.example/story\nInjected:header",
])
def test_gdelt_unsafe_article_urls_fail_source(url):
    with pytest.raises(ValueError):
        parse_gdelt_response(response(record(url=url)), retrieved_at=NOW)


def test_gdelt_invalid_article_cannot_be_silently_dropped_from_a_successful_source():
    with pytest.raises(ValueError):
        parse_gdelt_response(response(record(), record(seendate="invalid")), retrieved_at=NOW)
