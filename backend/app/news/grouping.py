"""Bounded English headline associations, never verified incidents or geocoding.

Only the city *mentions* below are recognized. Absence from this small vocabulary
reduces recall; it must not be repaired by guessing a country capital. Candidate
groups are recomputed with complete-link checks so one bridging article cannot
combine contradictory places, explicit dates, or reports more than 24 hours apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import re
import unicodedata

from app.news.models import NewsArticle, NewsEvent


GROUPING_VERSION = "headline-candidate-v1"
MAX_GROUP_ARTICLES = 250
MAX_INPUT_ARTICLES = 1000
MAX_TIME_SPAN = timedelta(hours=24)

# Text recognition only: this table contains no latitude, longitude, or implied
# incident location. Ambiguous Tripoli specifically requires its country in text.
CITY_MENTIONS = (
    "Abuja", "Accra", "Addis Ababa", "Aleppo", "Amman", "Ankara", "Athens", "Baghdad",
    "Bamako", "Bangkok", "Beijing", "Beirut", "Belgrade", "Berlin", "Bogota", "Brussels",
    "Bucharest", "Budapest", "Buenos Aires", "Cairo", "Cape Town", "Caracas", "Colombo",
    "Dakar", "Damascus", "Dhaka", "Doha", "Dubai", "Dublin", "Gaza", "Geneva", "Hanoi",
    "Harare", "Helsinki", "Hong Kong", "Islamabad", "Istanbul", "Jakarta", "Jerusalem",
    "Johannesburg", "Kabul", "Karachi", "Kathmandu", "Kharkiv", "Khartoum", "Kinshasa",
    "Kuala Lumpur", "Kyiv", "Lagos", "Lahore", "Lima", "Lisbon", "London", "Los Angeles",
    "Madrid", "Manila", "Mogadishu", "Moscow", "Mumbai", "Nairobi", "New Delhi",
    "New York", "Odesa", "Oslo", "Ottawa", "Ouagadougou", "Paris", "Port-au-Prince",
    "Prague", "Quito", "Rafah", "Ramallah", "Riga", "Rio de Janeiro", "Riyadh", "Rome",
    "Sanaa", "Sao Paulo", "Seoul", "Shanghai", "Singapore", "Stockholm",
    "Sydney", "Taipei", "Tehran", "Tel Aviv", "Tirana", "Tokyo", "Tunis", "Vienna",
    "Vilnius", "Warsaw", "Yangon", "Yerevan", "Zagreb", "Zurich",
)
CITY_ALIASES = {"kiev": "Kyiv", "odessa": "Odesa", "bogotá": "Bogota", "são paulo": "Sao Paulo", "sana'a": "Sanaa"}
COUNTRY_CLUES = (
    "Afghanistan", "Algeria", "Argentina", "Australia", "Bangladesh", "Belgium", "Brazil",
    "Canada", "Chile", "China", "Colombia", "Congo", "Egypt", "Ethiopia", "Finland", "France",
    "Germany", "Ghana", "Greece", "Haiti", "India", "Indonesia", "Iran", "Iraq", "Ireland",
    "Israel", "Italy", "Japan", "Jordan", "Kenya", "Lebanon", "Libya", "Malaysia", "Mali",
    "Mexico", "Myanmar", "Nepal", "Nigeria", "Norway", "Pakistan", "Palestine", "Peru",
    "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Saudi Arabia",
    "Senegal", "Serbia", "Somalia", "South Africa", "South Korea", "Spain", "Sri Lanka",
    "Sudan", "Sweden", "Switzerland", "Syria", "Taiwan", "Thailand", "Tunisia", "Turkey",
    "Ukraine", "United Kingdom", "United States", "Venezuela", "Vietnam", "Yemen", "Zimbabwe",
    # Explicit same-name-city disambiguators, not inferred countries.
    "Texas", "Ontario",
)
INCIDENT_WORDS = {
    "explosion": {"explosion", "explosions", "blast", "blasts", "bombing", "bombings"},
    "fire": {"fire", "fires", "blaze", "blazes", "wildfire", "wildfires"},
    "attack": {"attack", "attacks", "attacked", "strike", "strikes", "airstrike", "airstrikes"},
    "shooting": {"shooting", "shootings", "gunfire"},
    "flood": {"flood", "floods", "flooding"},
    "earthquake": {"earthquake", "earthquakes", "quake", "quakes"},
    "protest": {"protest", "protests", "demonstration", "demonstrations"},
    "outage": {"outage", "outages", "blackout", "blackouts"},
    "collision": {"collision", "collisions", "crash", "crashes"},
}
MONTHS = {name: index for index, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"), 1)}
MONTHS.update({name[:3]: number for name, number in list(MONTHS.items())})
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))
STOP_WORDS = set("""a an the this that these those at in near on of for from to and or but by with without
after before during as is are was were be been being has have had will would could can may might
new latest update updates news report reports reported reporting says say said official officials
breaking live today yesterday tomorrow overnight morning afternoon evening local world amid over
more most other another first last next two three people person injured killed dead death deaths
damaged damage damages hits hit incident incidents emergency emergencies rescue evacuation evacuated
plant facility airport port refinery city town capital region area building district county province
authorities police feared confirmed confirms suspected according details here's watch what why how
iranian israeli palestinian russian ukrainian american british french german chinese indian pakistani
libyan lebanese syrian turkish iraqi afghan african european asian australian canadian japanese
company corporation ministry government president minister military army naval air force
monday tuesday wednesday thursday friday saturday sunday january february march april june july
august september october november december jan feb mar apr jun jul aug sep oct nov dec""".split())
STOP_WORDS.update(word for variants in INCIDENT_WORDS.values() for word in variants)
STOP_WORDS.update(word for place in (*CITY_MENTIONS, *COUNTRY_CLUES, "Tripoli") for word in place.casefold().split())
HISTORICAL_OR_SPECULATIVE = re.compile(
    r"\b(?:anniversary|anniversaries|historical|history|retrospective|remembering|recalls|simulation|exercise|drill|"
    r"last year|years? ago|could happen|might happen|threatens? to|risk of|fear(?:s)? of)\b", re.IGNORECASE)


def _text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace("’", "'")


def _mentions(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_text(phrase)) + r"(?!\w)", text) is not None


def _places(text: str) -> tuple[str, ...]:
    places = {city for city in CITY_MENTIONS if _mentions(text, city)}
    places.update(city for alias, city in CITY_ALIASES.items() if _mentions(text, alias))
    if _mentions(text, "Tripoli"):
        countries = [country for country in ("Libya", "Lebanon") if _mentions(text, country)]
        places.add(f"Tripoli, {countries[0]}" if len(countries) == 1 else "Tripoli (ambiguous mention)")
    return tuple(sorted(places))


def _date_clues(text: str) -> dict[str, frozenset[str]]:
    days = set()
    for match in re.finditer(r"\b(?:19|20)\d{2}-(\d{2})-(\d{2})\b", text):
        days.add(f"{int(match[1])}-{int(match[2])}")
    for match in re.finditer(rf"\b({MONTH_PATTERN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", text):
        days.add(f"{MONTHS[match[1]]}-{int(match[2])}")
    for match in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})\b", text):
        days.add(f"{MONTHS[match[2]]}-{int(match[1])}")
    return {
        "day": frozenset(days),
        "year": frozenset(re.findall(r"\b(?:19|20)\d{2}\b", text)),
        "weekday": frozenset(re.findall(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)),
        # Preserve ambiguous numeric dates literally; never guess their locale.
        "numeric": frozenset(re.findall(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", text)),
    }


@dataclass(frozen=True)
class _Clues:
    article: NewsArticle
    places: tuple[str, ...]
    countries: frozenset[str]
    kind: str | None
    words: frozenset[str]
    entities: frozenset[str]
    dates: dict[str, frozenset[str]]
    time: datetime | None
    eligible: bool


def _clues(article: NewsArticle) -> _Clues:
    headline = article.headline
    text = _text(headline)
    places = _places(text)
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", headline)
    lowered = {_text(token) for token in tokens}
    kinds = [kind for kind, words in INCIDENT_WORDS.items() if lowered & words]
    words = frozenset(word for word in lowered if len(word) >= 4 and word not in STOP_WORDS)
    # This is a visible, fallible named-clue heuristic, not named-entity verification.
    # All/title-case copy does not supply a distinctive capitalization signal.
    content_tokens = [token for token in tokens if _text(token) in words]
    capitalized = [token for token in content_tokens if token[0].isupper()]
    entities = frozenset(_text(token) for token in capitalized) if content_tokens and len(capitalized) / len(content_tokens) <= 0.6 else frozenset()
    dates = _date_clues(text)
    provider_times = [observation.provider_timestamp for observation in article.observations if observation.provider_timestamp]
    time = article.published_at or (min(provider_times) if provider_times else article.first_seen_at)
    conflicting_provider_times = bool(provider_times and max(provider_times) - min(provider_times) > MAX_TIME_SPAN)
    unsupported_language = any(observation.language and observation.language.casefold() not in {"english", "en", "eng"}
                               for observation in article.observations)
    eligible = (len(places) == 1 and "ambiguous mention" not in places[0] and len(kinds) == 1
                and len(words) >= 2 and bool(entities) and time is not None
                and not conflicting_provider_times and not unsupported_language
                and not HISTORICAL_OR_SPECULATIVE.search(text) and all(len(values) <= 1 for values in dates.values()))
    return _Clues(article, places, frozenset(country for country in COUNTRY_CLUES if _mentions(text, country)),
                  kinds[0] if len(kinds) == 1 else None, words, entities, dates, time, bool(eligible))


def _compatible(left: _Clues, right: _Clues) -> bool:
    if not left.eligible or not right.eligible or left.places != right.places or left.kind != right.kind:
        return False
    if left.time is None or right.time is None or abs(left.time - right.time) > MAX_TIME_SPAN:
        return False
    if left.countries and right.countries and left.countries != right.countries:
        return False
    if any(left.dates[kind] and right.dates[kind] and left.dates[kind] != right.dates[kind] for kind in left.dates):
        return False
    return len(left.words & right.words) >= 2 and bool(left.entities & right.entities)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()[:24]


def _event(group: list[_Clues]) -> NewsEvent:
    articles = sorted((item.article for item in group), key=lambda article: article.id)
    candidate = len(articles) > 1
    places = sorted({place for clue in group for place in clue.places})
    revision = _digest({"policy": GROUPING_VERSION, "articles": [
        {"id": article.id, "url": article.canonical_url, "headline": article.headline,
         "publisher_id": article.publisher_id, "published_at": article.published_at.isoformat() if article.published_at else None,
         "first_seen_at": article.first_seen_at.isoformat() if article.first_seen_at else None,
         "observations": sorted((observation.provider_id, observation.provider_timestamp.isoformat() if observation.provider_timestamp else "",
                                 observation.language or "") for observation in article.observations),
         "syndication_key": article.syndication_key} for article in articles]})
    basis = ("Candidate association only: one matching city mention, incident type, a shared capitalized named clue and at least two content clues; "
             "all pairs pass a 24-hour publication/provider/collection-time window and explicit date/place conflict checks. "
             "Provider and collection times are only heuristics, not publication or incident times. Distinct URLs can contain shared copy; publisher breadth is not independent confirmation. "
             "English headline rules and a limited city vocabulary can miss or misassociate reporting; no incident coordinates are inferred.") if candidate else (
        "Single collected publication; no supported cross-publisher event association. English headline rules and a limited city vocabulary do not cover every place or language. "
        "Any listed place is an unverified headline mention, not incident geography. Provider and collection times are not publication or incident times.")
    return NewsEvent(
        id=f"news-{'candidate' if candidate else 'article'}-{_digest([GROUPING_VERSION, [article.id for article in articles]])}",
        title=articles[0].headline,
        summary=("Potentially related collected headlines. Read each original source to assess what happened; this association and its location are unverified."
                 if candidate else "Collected publisher headline and source link. The publication does not establish a verified incident or map location."),
        category=group[0].kind or "News report", status="unconfirmed" if candidate else "reported",
        severity="unknown", severity_basis="No physical severity is inferred from headlines, article volume, publisher count, or provider annotations.",
        grouping_basis=basis, grouping_status="candidate" if candidate else "single_source", grouping_version=GROUPING_VERSION,
        assignment_revision=revision, place_hints=places[:8], location=None, scope="unlocated", is_demo=False, articles=articles,
    )


def group_candidate_events(articles: list[NewsArticle], *, previous_events: list[NewsEvent] | None = None) -> list[NewsEvent]:
    """Associate canonical publisher articles; each retained identity occurs once.

    Canonical URL and provider-observation merging must happen before this boundary.
    Repeating an identical object is harmless; conflicting identities are rejected.
    Prior candidate IDs can follow the strongest overlap after all current checks
    pass; assignment_revision always describes the current membership and evidence.
    """
    if len(articles) > MAX_INPUT_ARTICLES:
        raise ValueError("Candidate grouping input exceeds the 1000 article bound")
    unique: dict[str, NewsArticle] = {}
    urls: dict[str, str] = {}
    for article in articles:
        if article.is_demo or article.record_kind != "article" or article.canonical_url is None:
            raise ValueError("Candidate grouping accepts actual publisher articles only")
        if article.id in unique:
            if unique[article.id] != article:
                raise ValueError("Conflicting article identity requires upstream reconciliation")
            continue
        if article.canonical_url in urls:
            raise ValueError("Duplicate canonical URL requires upstream observation merging")
        unique[article.id] = article
        urls[article.canonical_url] = article.id

    groups: list[list[_Clues]] = []
    for article in sorted(unique.values(), key=lambda item: item.id):
        clue = _clues(article)
        for group in groups:
            common_words = clue.words.intersection(*(member.words for member in group))
            common_entities = clue.entities.intersection(*(member.entities for member in group))
            if (len(group) < MAX_GROUP_ARTICLES and len(common_words) >= 2 and common_entities
                    and all(_compatible(clue, member) for member in group)):
                group.append(clue)
                break
        else:
            groups.append([clue])
    # A publisher's multiple updates alone are not a cross-publisher association.
    events = []
    for group in groups:
        if len({item.article.publisher_id for item in group}) < 2:
            events.extend(_event([item]) for item in group)
        else:
            events.append(_event(group))

    previous = {event.id: event for event in previous_events or []
                if not event.is_demo and event.grouping_status == "candidate" and event.grouping_version == GROUPING_VERSION}
    matches = []
    for event in events:
        if event.grouping_status != "candidate":
            continue
        identities = {article.id for article in event.articles}
        for old in previous.values():
            overlap = len(identities & {article.id for article in old.articles})
            if overlap >= 2 and event.place_hints == old.place_hints and event.category == old.category:
                matches.append((-overlap, old.id, event.id))
    assigned_previous, assigned_current = set(), set()
    replacements = {}
    for _, previous_id, current_id in sorted(matches):
        if previous_id not in assigned_previous and current_id not in assigned_current:
            assigned_previous.add(previous_id)
            assigned_current.add(current_id)
            replacements[current_id] = previous_id
    return sorted((event.model_copy(update={"id": replacements.get(event.id, event.id)}) for event in events), key=lambda event: event.id)
