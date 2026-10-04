"""Bounded English headline associations and approximate place references.

Only the place *mentions* in the gazetteer are recognized. A headline that names
one recognized place alongside an incident word is given that place's reference
point, labeled as an approximate, low-confidence headline mention. It is never a
verified incident site, and a country mention is placed at the country's rough
centre, not its capital. Candidate groups are recomputed with complete-link
checks so one bridging article cannot combine different places, explicit dates,
or reports more than 24 hours apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import re
import unicodedata

from app.news.gazetteer import CITY_ALIASES, CITY_POINTS, COUNTRY_POINTS
from app.news.models import NewsArticle, NewsEvent, NewsLocation


GROUPING_VERSION = "headline-place-v2"
MAX_GROUP_ARTICLES = 250
MAX_INPUT_ARTICLES = 1000
MAX_TIME_SPAN = timedelta(hours=24)

# Ambiguous Tripoli specifically requires its country in text.
CITY_MENTIONS = tuple(city for city in CITY_POINTS if not city.startswith("Tripoli"))
# Explicit same-name-city disambiguators, not inferred countries. Their presence blocks a map position.
PLACE_QUALIFIERS = (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
    "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Wisconsin", "Wyoming",
    "Alberta", "British Columbia", "Manitoba", "Nova Scotia", "Ontario", "Quebec", "Saskatchewan",
)
COUNTRY_CLUES = (*COUNTRY_POINTS, *PLACE_QUALIFIERS)
# Ordered: when a headline uses several incident words, the first matching kind names the event.
INCIDENT_WORDS = {
    "attack": {"attack", "attacks", "attacked", "strike", "strikes", "airstrike", "airstrikes", "missile", "missiles",
               "drone", "drones", "shelling", "shelled", "bomb", "bombs", "bombed", "bombing", "bombings", "rocket", "rockets",
               "struck", "raid", "raids", "ambush", "ambushed", "assault", "offensive", "massacre", "hostage", "hostages"},
    "explosion": {"explosion", "explosions", "blast", "blasts", "explodes", "exploded"},
    "shooting": {"shooting", "shootings", "gunfire", "gunman", "gunmen"},
    "unrest": {"riot", "riots", "rioting", "clashes", "unrest", "coup"},
    "protest": {"protest", "protests", "protesters", "demonstration", "demonstrations"},
    "fire": {"fire", "fires", "blaze", "blazes", "wildfire", "wildfires"},
    "flood": {"flood", "floods", "flooding"},
    "earthquake": {"earthquake", "earthquakes", "quake", "quakes"},
    "outage": {"outage", "outages", "blackout", "blackouts"},
    "collision": {"collision", "collisions", "crash", "crashes"},
}
# Common non-incident uses of incident words. Fallible and English-only: it reduces, not removes, false matches.
NOT_AN_INCIDENT = re.compile(
    r"\b(?:heart attacks?|panic attacks?|attack ads?|on strike|strike action|hunger strikes?|"
    r"(?:labou?r|union|workers?|teachers?|doctors?|nurses?|transit|rail|train|bus|pilots?|general|writers?|actors?|port|dock) strikes?|"
    r"strikes? (?:a )?(?:deal|balance|tone|chord|gold|late|early|first|twice|back|again)|fires? (?:coach|manager|ceo|chief|minister|staff|employees?|workers?)|"
    r"under fire|fire sale|market crash|stock crash|crash(?:es)? out|flood(?:s|ing)? of|box office|"
    r"goals?|striker|cup|league|match|odi|wickets?|innings|playoffs?|championship|touchdown|quarterback)\b", re.IGNORECASE)
# Publication and place names that contain another place's name; removed before place recognition.
NOT_A_PLACE = re.compile(
    r"\b(?:new york times|new york post|new yorker|times of india|times of israel|jerusalem post|moscow times|kyiv independent|kyiv post|"
    r"tehran times|south china morning post|hong kong free press|new mexico|new south wales|west indies|paris agreement|geneva conventions?)\b")
# Words that introduce the place an incident is reported at, used only to choose between several mentions.
TARGETING = (r"(?:in|near|at|on|outside|across|hits?|strikes?|struck|bombs?|bombed|attacks?|attacked|shells?|shelled|"
             r"targets?|targeted|rocks?|rocked|pounds?|pounded)\s+(?:the\s+)?"
             r"(?:(?:central|northern|southern|eastern|western|downtown|occupied|[a-z]\s*\.)\s+)?")
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


@dataclass(frozen=True)
class _Place:
    label: str
    lat: float
    lon: float
    level: str  # "city" or "country"


def _targeted(text: str, names: list[str]) -> list[str]:
    def spellings(name: str) -> list[str]:
        return [name.split(",")[0], *(alias for alias, city in CITY_ALIASES.items() if city == name)]
    return [name for name in names if any(
        re.search(r"(?<!\w)" + TARGETING + re.escape(_text(spelling)) + r"(?!\w)", text) for spelling in spellings(name))]


def _resolve_place(text: str, places: tuple[str, ...], countries: frozenset[str]) -> _Place | None:
    """One unambiguous named place, or nothing. Several mentions need an explicit targeting word."""
    if any(qualifier in countries for qualifier in PLACE_QUALIFIERS) or any("ambiguous mention" in place for place in places):
        return None
    if places:
        chosen = list(places) if len(places) == 1 else _targeted(text, list(places))
        if len(chosen) != 1:
            return None
        lat, lon, country = CITY_POINTS[chosen[0]]
        label = chosen[0] if "," in chosen[0] or chosen[0] == country else f"{chosen[0]}, {country}"
        return _Place(label, lat, lon, "city")
    # A country is broad and often names an actor or destination, so it must be targeted or lead the headline.
    named = sorted(country for country in countries if country in COUNTRY_POINTS)
    chosen = _targeted(text, named)
    if not chosen:  # "in Ras al-Maara, Syria": an unrecognized locality qualified by its country.
        chosen = [country for country in named
                  if re.search(r"(?<!\w)(?:in|near|at)\s+[^.;:]{2,60}?,\s+" + re.escape(_text(country)) + r"(?!\w)", text)]
    if not chosen and len(named) == 1 and text.startswith(_text(named[0])):
        chosen = named
    if len(chosen) != 1:
        return None
    lat, lon = COUNTRY_POINTS[chosen[0]]
    return _Place(chosen[0], lat, lon, "country")


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
    dates: dict[str, frozenset[str]]
    time: datetime | None
    place: _Place | None
    eligible: bool


def _clues(article: NewsArticle) -> _Clues:
    headline, _, outlet = article.headline.partition(" | ")  # A trailing publisher name is not part of the report.
    text = NOT_A_PLACE.sub(" ", _text(headline)).strip()
    # An outlet named after the same town ("Athens News Courier") signals a local story, not the well-known city.
    places = tuple(place for place in _places(text) if not _mentions(_text(outlet), place.split(",")[0]))
    countries = frozenset(country for country in COUNTRY_CLUES if _mentions(text, country))
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", headline)
    lowered = {_text(token) for token in tokens}
    kinds = [kind for kind, words in INCIDENT_WORDS.items() if lowered & words]
    reported = bool(kinds) and not NOT_AN_INCIDENT.search(text) and not HISTORICAL_OR_SPECULATIVE.search(text)
    words = frozenset(word for word in lowered if len(word) >= 4 and word not in STOP_WORDS)
    dates = _date_clues(text)
    provider_times = [observation.provider_timestamp for observation in article.observations if observation.provider_timestamp]
    time = article.published_at or (min(provider_times) if provider_times else article.first_seen_at)
    conflicting_provider_times = bool(provider_times and max(provider_times) - min(provider_times) > MAX_TIME_SPAN)
    unsupported_language = any(observation.language and observation.language.casefold() not in {"english", "en", "eng"}
                               for observation in article.observations)
    # A place is only attached to a headline that reports an incident now, not to any story naming a place.
    place = _resolve_place(text, places, countries) if reported else None
    eligible = (place is not None and time is not None and not conflicting_provider_times and not unsupported_language
                and all(len(values) <= 1 for values in dates.values()))
    return _Clues(article, places, countries, kinds[0] if reported else None, words, dates, time, place, bool(eligible))


def placed_country(article: NewsArticle) -> str | None:
    """The country of the place this headline would be placed at, or None when it would stay unlocated."""
    place = _clues(article).place
    if place is None:
        return None
    return place.label.rsplit(", ", 1)[-1] if place.level == "city" else place.label


def _compatible(left: _Clues, right: _Clues) -> bool:
    if not left.eligible or not right.eligible or left.place != right.place or left.kind != right.kind:
        return False
    if left.time is None or right.time is None or abs(left.time - right.time) > MAX_TIME_SPAN:
        return False
    if any(left.dates[kind] and right.dates[kind] and left.dates[kind] != right.dates[kind] for kind in left.dates):
        return False
    # A whole country is too broad to assume one incident; require shared headline content as well.
    return left.place.level == "city" or len(left.words & right.words) >= 2


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()[:24]


def _location(place: _Place, source_url: str | None) -> NewsLocation:
    if place.level == "city":
        return NewsLocation(
            lat=place.lat, lon=place.lon, label=f"{place.label} (place named in headline)",
            precision="approximate_area", confidence="low", source_url=source_url,
            basis=("The headline names this city alongside an incident word. The marker is the city's reference point, "
                   "not a verified incident site; the report may concern a nearby area or only mention the city."))
    return NewsLocation(
        lat=place.lat, lon=place.lon, label=f"{place.label} (country named in headline)",
        precision="approximate_area", confidence="low", source_url=source_url,
        basis=("The headline names only this country alongside an incident word. The marker is the country's rough "
               "geographic centre, not its capital and not an incident site; the place within the country is unknown."))


def _event(group: list[_Clues]) -> NewsEvent:
    articles = sorted((item.article for item in group), key=lambda article: article.id)
    candidate = len(articles) > 1
    places = sorted({place for clue in group for place in clue.places})
    place = group[0].place
    revision = _digest({"policy": GROUPING_VERSION, "articles": [
        {"id": article.id, "url": article.canonical_url, "headline": article.headline,
         "publisher_id": article.publisher_id, "published_at": article.published_at.isoformat() if article.published_at else None,
         "first_seen_at": article.first_seen_at.isoformat() if article.first_seen_at else None,
         "observations": sorted((observation.provider_id, observation.provider_timestamp.isoformat() if observation.provider_timestamp else "",
                                 observation.language or "") for observation in article.observations),
         "syndication_key": article.syndication_key} for article in articles]})
    basis = ("Candidate association only: the headlines name the same place and the same incident type, and all pairs pass a "
             "24-hour publication/provider/collection-time window and explicit date conflict checks; country-level matches also share headline content. "
             "Separate incidents in one place on one day can be combined. Provider and collection times are only heuristics, not publication or incident times. "
             "Distinct URLs can contain shared copy; publisher breadth is not independent confirmation. "
             "English headline rules and a limited place vocabulary can miss or misassociate reporting.") if candidate else (
        "Single collected publication; no cross-publisher event association. English headline rules and a limited place vocabulary do not cover every place or language. "
        "Any listed place is a headline mention, not verified incident geography. Provider and collection times are not publication or incident times.")
    if place is not None:
        summary = ("Collected headlines that name the same place and incident type. Read each original source to assess what happened; "
                   "the association is unverified and the map position is the named place, not a confirmed site." if candidate else
                   "Collected publisher headline and source link. The map position is the place named in the headline, not a confirmed incident site.")
    else:
        summary = "Collected publisher headline and source link. The publication does not establish a verified incident or map location."
    return NewsEvent(
        id=f"news-{'candidate' if candidate else 'article'}-{_digest([GROUPING_VERSION, [article.id for article in articles]])}",
        title=articles[0].headline, summary=summary,
        category=group[0].kind or "News report", status="unconfirmed" if candidate else "reported",
        severity="unknown", severity_basis="No physical severity is inferred from headlines, article volume, publisher count, or provider annotations.",
        grouping_basis=basis, grouping_status="candidate" if candidate else "single_source", grouping_version=GROUPING_VERSION,
        assignment_revision=revision, place_hints=places[:8],
        location=_location(place, articles[0].canonical_url) if place is not None else None,
        scope="located" if place is not None else "unlocated", is_demo=False, articles=articles,
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
            if len(group) < MAX_GROUP_ARTICLES and all(_compatible(clue, member) for member in group):
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
