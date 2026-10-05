"""Regenerate app/news/gazetteer_natural_earth.py from pinned Natural Earth files.

Usage: python scripts/build_gazetteer.py PLACES.geojson COUNTRIES.geojson

Both inputs are public-domain Natural Earth 1:50m layers at the commit recorded
in SOURCE below; the script checks their SHA-256 before writing. It keeps only
place names a headline can name unambiguously and records why others are left out.
"""

import hashlib
import json
import pprint
import re
import sys
import unicodedata
from pathlib import Path

COMMIT = "693f11422f4e08d2da4566b854dda53eb7c39fb3"
BASE = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{COMMIT}/geojson/"
PLACES_SHA256 = "46e89429a78d5156cebe876d7011ec25d50003233f6d382dc8fd0ffd11d784b5"
COUNTRIES_SHA256 = "2a6a5c1ab0ba1e7faa90e686a0500e08fb100d154c5b9ef37e9328991d4da2e5"
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "news" / "gazetteer_natural_earth.py"

# Natural Earth long names that headlines rarely use, mapped to the common English name.
COUNTRY_NAMES = {
    "Republic of Korea": "South Korea", "Dem. Rep. Korea": "North Korea", "Russian Federation": "Russia",
    "Lao PDR": "Laos", "Czech Republic": "Czechia", "Republic of Cabo Verde": "Cabo Verde",
    "Brunei Darussalam": "Brunei", "The Gambia": "Gambia", "Democratic Republic of the Congo": "DR Congo",
    "Republic of the Congo": "Republic of the Congo", "Côte d'Ivoire": "Ivory Coast", "Faeroe Islands": "Faroe Islands",
}
# Headline names that are also everyday English words, common personal names, or
# metonyms for a government more often than a place. Excluded from city matching.
NOT_PLACE_NAMES = {
    "Male", "Nice", "Split", "Mobile", "Reading", "Bath", "Hope", "Victoria", "Hamilton", "Jackson", "Lincoln",
    "Austin", "Charlotte", "Madison", "Raleigh", "Augusta", "Columbus", "Washington", "Hull", "Sale", "Of",
    "Bar", "Sur", "Kansas City", "Orange", "Florence", "Phoenix", "Concord", "Providence", "Independence",
    "Liberty", "Mercedes", "Santa Fe", "Salem", "Trinidad", "George Town", "Georgetown", "Cork", "Derby",
    "Wellington", "Darwin", "Marshall", "Jordan", "Chad", "Cameron", "Tyler", "Lyon", "Mons", "Pau", "Ica",
    "Bo", "Kut", "Lae", "Hilo", "Kiel", "Ely", "Bend", "Eugene", "Laredo", "Manchester", "Boston", "Dayton",
    "Sherbrooke", "Kingston", "Richmond", "Jamestown", "Monroe", "Lafayette", "Montgomery", "Little Rock",
    "Springfield", "Paris", "Mary", "David", "Nancy", "Douglas", "Regina", "Helena", "Pierre", "Columbia",
    "Churchill", "Stanley", "Norfolk", "Natal", "Eureka", "Formosa", "Resolute", "Thompson", "Brandon", "Griffith",
    "Katherine", "Bethel", "Buffalo", "Kodiak", "Valdez", "León", "Bismarck", "Casper", "Billings", "Olympia",
    "Savannah", "Orlando", "Bose", "Tripoli", "Gold Coast",
}
# A US state shares the name, so a bare mention is not evidence of the country.
NOT_COUNTRY_NAMES = {"Georgia"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ascii_fold(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()


def ring_area_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    area /= 2
    if not area:
        return 0.0, ring[0][0], ring[0][1]
    return abs(area), cx / (6 * area), cy / (6 * area)


def inside(ring: list[list[float]], x: float, y: float) -> bool:
    result = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            result = not result
    return result


def country_centre(geometry: dict) -> tuple[float, float] | None:
    """Area centroid of the largest polygon; omitted when it falls outside that polygon."""
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    area, lon, lat = max((ring_area_centroid(polygon[0]) for polygon in polygons), key=lambda item: item[0])
    largest = max(polygons, key=lambda polygon: ring_area_centroid(polygon[0])[0])
    return (round(lat, 1), round(lon, 1)) if inside(largest[0], lon, lat) else None


def main(places_path: Path, countries_path: Path) -> None:
    if sha256(places_path) != PLACES_SHA256 or sha256(countries_path) != COUNTRIES_SHA256:
        raise SystemExit("Input files do not match the pinned Natural Earth hashes")
    countries: dict[str, tuple[float, float]] = {}
    skipped_countries = []
    for feature in json.loads(countries_path.read_text("utf-8"))["features"]:
        props = feature["properties"]
        if props["TYPE"] not in {"Sovereign country", "Country"}:
            continue
        name = COUNTRY_NAMES.get(props["NAME_LONG"], props["NAME_LONG"])
        if name in NOT_COUNTRY_NAMES:
            continue
        centre = country_centre(feature["geometry"])
        if centre is None:
            skipped_countries.append(name)
        else:
            countries[name] = centre
    country_by_a3 = {}
    for feature in json.loads(countries_path.read_text("utf-8"))["features"]:
        props = feature["properties"]
        country_by_a3[props["ADM0_A3"]] = COUNTRY_NAMES.get(props["NAME_LONG"], props["NAME_LONG"])

    raw = [feature["properties"] for feature in json.loads(places_path.read_text("utf-8"))["features"]]
    counts: dict[str, int] = {}
    for props in raw:
        counts[props["name"]] = counts.get(props["name"], 0) + 1
    names = {props["name"] for props in raw}
    blocked = NOT_PLACE_NAMES
    others = [*names, *countries]
    cities: dict[str, tuple[float, float, str]] = {}
    aliases: dict[str, str] = {}
    for props in sorted(raw, key=lambda item: item["name"]):
        name = props["name"]
        # Research stations south of 60°S are not places headlines name for incidents.
        if counts[name] > 1 or name in blocked or len(name) < 4 or name in countries or "," in name or props["latitude"] < -60:
            continue
        # A name inside a longer place name ("York" in "New York") would double-match.
        pattern = re.compile(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)")
        if any(other != name and pattern.search(other.casefold()) for other in others):
            continue
        country = country_by_a3.get(props["adm0_a3"]) or props["adm0name"]
        cities[name] = (round(props["latitude"], 2), round(props["longitude"], 2), country)
        folded = ascii_fold(name)
        if folded != name and folded not in names:
            aliases[folded.casefold()] = name

    header = (
        '"""Generated by scripts/build_gazetteer.py from Natural Earth 1:50m data (public domain). Do not edit.\n\n'
        "City points are populated-place reference points; country points are the area centroid of each\n"
        "country's largest polygon. Neither is an incident location.\n"
        '"""\n\n'
    )
    body = (
        f"SOURCE = {pprint.pformat({'places': BASE + 'ne_50m_populated_places_simple.geojson', 'places_sha256': PLACES_SHA256, 'countries': BASE + 'ne_50m_admin_0_countries.geojson', 'countries_sha256': COUNTRIES_SHA256, 'commit': COMMIT, 'terms': 'https://www.naturalearthdata.com/about/terms-of-use/'}, width=120)}\n\n"
        f"CITY_POINTS: dict[str, tuple[float, float, str]] = {pprint.pformat(cities, width=120)}\n\n"
        f"CITY_ALIASES: dict[str, str] = {pprint.pformat(aliases, width=120)}\n\n"
        f"COUNTRY_POINTS: dict[str, tuple[float, float]] = {pprint.pformat(countries, width=120)}\n"
    )
    OUTPUT.write_text(header + body, "utf-8")
    print(f"{len(cities)} cities, {len(aliases)} aliases, {len(countries)} countries; no centre for: {', '.join(skipped_countries) or 'none'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
