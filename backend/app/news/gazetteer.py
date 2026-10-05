"""Approximate reference points for places named in headlines.

A point here is where a named city or country is, never where an incident
happened. City points are city centres; country points are rough geographic
centres, not capitals. Consumers must label any position derived from this
table as an approximate headline place mention with low confidence.

The hand-curated tables below take precedence. Natural Earth populated places and
country centroids (see gazetteer_natural_earth.py) fill in the rest, minus any name
that would double-match a curated place or its alternative spelling.
"""

from math import asin, cos, radians, sin, sqrt

from app.news import gazetteer_natural_earth as natural_earth

# City -> (latitude, longitude, country). Tripoli is ambiguous without its country.
CURATED_CITY_POINTS: dict[str, tuple[float, float, str]] = {
    "Abu Dhabi": (24.45, 54.38, "United Arab Emirates"), "Abuja": (9.06, 7.49, "Nigeria"),
    "Accra": (5.56, -0.20, "Ghana"), "Addis Ababa": (9.01, 38.76, "Ethiopia"), "Aden": (12.79, 45.02, "Yemen"),
    "Aleppo": (36.20, 37.16, "Syria"), "Amman": (31.95, 35.93, "Jordan"), "Ankara": (39.93, 32.86, "Turkey"),
    "Athens": (37.98, 23.73, "Greece"), "Baghdad": (33.31, 44.37, "Iraq"), "Baku": (40.41, 49.87, "Azerbaijan"),
    "Bamako": (12.64, -8.00, "Mali"), "Bangkok": (13.76, 100.50, "Thailand"), "Basra": (30.51, 47.78, "Iraq"),
    "Beijing": (39.90, 116.41, "China"), "Beirut": (33.89, 35.50, "Lebanon"), "Belgorod": (50.60, 36.59, "Russia"),
    "Belgrade": (44.79, 20.45, "Serbia"), "Benghazi": (32.12, 20.09, "Libya"), "Berlin": (52.52, 13.40, "Germany"),
    "Bogota": (4.71, -74.07, "Colombia"), "Brussels": (50.85, 4.35, "Belgium"), "Bryansk": (53.24, 34.36, "Russia"),
    "Bucharest": (44.43, 26.10, "Romania"), "Budapest": (47.50, 19.04, "Hungary"),
    "Buenos Aires": (-34.60, -58.38, "Argentina"), "Cairo": (30.04, 31.24, "Egypt"),
    "Cape Town": (-33.92, 18.42, "South Africa"), "Caracas": (10.48, -66.90, "Venezuela"),
    "Chernihiv": (51.49, 31.29, "Ukraine"), "Chisinau": (47.01, 28.86, "Moldova"), "Colombo": (6.93, 79.86, "Sri Lanka"),
    "Dakar": (14.72, -17.47, "Senegal"), "Damascus": (33.51, 36.28, "Syria"), "Dhaka": (23.81, 90.41, "Bangladesh"),
    "Dnipro": (48.46, 35.05, "Ukraine"), "Doha": (25.29, 51.53, "Qatar"), "Donetsk": (48.02, 37.80, "Ukraine"),
    "Dubai": (25.20, 55.27, "United Arab Emirates"), "Dublin": (53.35, -6.26, "Ireland"),
    "El Fasher": (13.63, 25.35, "Sudan"), "Erbil": (36.19, 44.01, "Iraq"), "Gaza": (31.50, 34.47, "Palestine"),
    "Geneva": (46.20, 6.14, "Switzerland"), "Goma": (-1.66, 29.22, "Congo"), "Haifa": (32.79, 34.99, "Israel"),
    "Hanoi": (21.03, 105.85, "Vietnam"), "Harare": (-17.83, 31.05, "Zimbabwe"), "Havana": (23.11, -82.37, "Cuba"),
    "Helsinki": (60.17, 24.94, "Finland"), "Hodeidah": (14.80, 42.95, "Yemen"), "Homs": (34.73, 36.71, "Syria"),
    "Hong Kong": (22.32, 114.17, "China"), "Idlib": (35.93, 36.63, "Syria"), "Isfahan": (32.65, 51.67, "Iran"),
    "Islamabad": (33.68, 73.05, "Pakistan"), "Istanbul": (41.01, 28.98, "Turkey"), "Jakarta": (-6.21, 106.85, "Indonesia"),
    "Jeddah": (21.49, 39.19, "Saudi Arabia"), "Jenin": (32.46, 35.30, "Palestine"), "Jerusalem": (31.77, 35.21, "Israel"),
    "Johannesburg": (-26.20, 28.05, "South Africa"), "Juba": (4.85, 31.58, "South Sudan"),
    "Kabul": (34.56, 69.21, "Afghanistan"), "Kampala": (0.35, 32.58, "Uganda"), "Kandahar": (31.63, 65.71, "Afghanistan"),
    "Karachi": (24.86, 67.00, "Pakistan"), "Kathmandu": (27.72, 85.32, "Nepal"), "Kazan": (55.80, 49.11, "Russia"),
    "Khan Younis": (31.35, 34.30, "Palestine"), "Kharkiv": (49.99, 36.23, "Ukraine"), "Khartoum": (15.50, 32.56, "Sudan"),
    "Kherson": (46.64, 32.62, "Ukraine"), "Kinshasa": (-4.44, 15.27, "Congo"), "Kuala Lumpur": (3.14, 101.69, "Malaysia"),
    "Kursk": (51.73, 36.19, "Russia"), "Kuwait City": (29.38, 47.98, "Kuwait"), "Kyiv": (50.45, 30.52, "Ukraine"),
    "Lagos": (6.52, 3.38, "Nigeria"), "Lahore": (31.55, 74.34, "Pakistan"), "Lima": (-12.05, -77.04, "Peru"),
    "Lisbon": (38.72, -9.14, "Portugal"), "London": (51.51, -0.13, "United Kingdom"),
    "Los Angeles": (34.05, -118.24, "United States"), "Luhansk": (48.57, 39.31, "Ukraine"), "Lviv": (49.84, 24.03, "Ukraine"),
    "Madrid": (40.42, -3.70, "Spain"), "Maiduguri": (11.83, 13.15, "Nigeria"), "Manama": (26.23, 50.59, "Bahrain"),
    "Manila": (14.60, 120.98, "Philippines"), "Mariupol": (47.10, 37.54, "Ukraine"),
    "Mexico City": (19.43, -99.13, "Mexico"), "Minsk": (53.90, 27.57, "Belarus"), "Mogadishu": (2.05, 45.32, "Somalia"),
    "Moscow": (55.76, 37.62, "Russia"), "Mosul": (36.34, 43.13, "Iraq"), "Mumbai": (19.08, 72.88, "India"),
    "Muscat": (23.59, 58.41, "Oman"), "Mykolaiv": (46.98, 31.99, "Ukraine"), "Nablus": (32.22, 35.26, "Palestine"),
    "Nairobi": (-1.29, 36.82, "Kenya"), "New Delhi": (28.61, 77.21, "India"), "New York": (40.71, -74.01, "United States"),
    "Niamey": (13.51, 2.11, "Niger"), "Odesa": (46.48, 30.72, "Ukraine"), "Oslo": (59.91, 10.75, "Norway"),
    "Ottawa": (45.42, -75.70, "Canada"), "Ouagadougou": (12.37, -1.52, "Burkina Faso"), "Paris": (48.86, 2.35, "France"),
    "Peshawar": (34.01, 71.58, "Pakistan"), "Port-au-Prince": (18.59, -72.31, "Haiti"),
    "Prague": (50.08, 14.44, "Czech Republic"), "Pyongyang": (39.04, 125.76, "North Korea"),
    "Quetta": (30.18, 67.00, "Pakistan"), "Quito": (-0.18, -78.47, "Ecuador"), "Rafah": (31.29, 34.25, "Palestine"),
    "Ramallah": (31.90, 35.20, "Palestine"), "Riga": (56.95, 24.11, "Latvia"), "Rio de Janeiro": (-22.91, -43.17, "Brazil"),
    "Riyadh": (24.71, 46.68, "Saudi Arabia"), "Rome": (41.90, 12.50, "Italy"), "Rostov-on-Don": (47.24, 39.70, "Russia"),
    "Sanaa": (15.37, 44.19, "Yemen"), "Sao Paulo": (-23.55, -46.63, "Brazil"), "Seoul": (37.57, 126.98, "South Korea"),
    "Sevastopol": (44.62, 33.53, "Ukraine"), "Shanghai": (31.23, 121.47, "China"), "Singapore": (1.35, 103.82, "Singapore"),
    "Srinagar": (34.08, 74.80, "India"), "St Petersburg": (59.93, 30.34, "Russia"), "Stockholm": (59.33, 18.07, "Sweden"),
    "Sumy": (50.91, 34.80, "Ukraine"), "Sydney": (-33.87, 151.21, "Australia"), "Taipei": (25.03, 121.57, "Taiwan"),
    "Tbilisi": (41.72, 44.79, "Georgia"), "Tehran": (35.69, 51.39, "Iran"), "Tel Aviv": (32.09, 34.78, "Israel"),
    "Tirana": (41.33, 19.82, "Albania"), "Tokyo": (35.68, 139.69, "Japan"), "Tripoli, Lebanon": (34.44, 35.85, "Lebanon"),
    "Tripoli, Libya": (32.89, 13.19, "Libya"), "Tunis": (36.81, 10.18, "Tunisia"), "Vienna": (48.21, 16.37, "Austria"),
    "Vilnius": (54.69, 25.28, "Lithuania"), "Warsaw": (52.23, 21.01, "Poland"), "Yangon": (16.84, 96.17, "Myanmar"),
    "Yerevan": (40.18, 44.51, "Armenia"), "Zagreb": (45.81, 15.98, "Croatia"), "Zaporizhzhia": (47.84, 35.14, "Ukraine"),
    "Zurich": (47.38, 8.54, "Switzerland"),
}

CURATED_CITY_ALIASES = {
    "kiev": "Kyiv", "odessa": "Odesa", "bogotá": "Bogota", "são paulo": "Sao Paulo", "sana'a": "Sanaa",
    "saint petersburg": "St Petersburg", "st. petersburg": "St Petersburg", "khan yunis": "Khan Younis",
    "hodeida": "Hodeidah", "kharkov": "Kharkiv", "zaporizhia": "Zaporizhzhia", "gaza city": "Gaza",
    "al-fashir": "El Fasher", "el-fasher": "El Fasher",
}

# Country -> rough geographic centre. Deliberately not the capital.
CURATED_COUNTRY_POINTS: dict[str, tuple[float, float]] = {
    "Afghanistan": (33.9, 67.7), "Algeria": (28.0, 2.6), "Argentina": (-35.4, -65.2), "Armenia": (40.3, 44.9),
    "Australia": (-25.3, 133.8), "Azerbaijan": (40.3, 47.7), "Bahrain": (26.0, 50.55), "Bangladesh": (23.7, 90.3),
    "Belarus": (53.5, 28.0), "Belgium": (50.6, 4.6), "Brazil": (-10.8, -52.9), "Burkina Faso": (12.3, -1.7),
    "Cameroon": (5.7, 12.7), "Canada": (57.0, -101.0), "Chile": (-35.7, -71.2), "China": (35.5, 103.9),
    "Colombia": (3.9, -73.1), "Congo": (-2.9, 23.6), "Cuba": (21.6, -79.0), "Ecuador": (-1.4, -78.4),
    "Egypt": (26.5, 29.9), "Ethiopia": (9.0, 39.6), "Finland": (64.3, 26.0), "France": (46.6, 2.5),
    "Germany": (51.1, 10.4), "Ghana": (7.9, -1.2), "Greece": (39.3, 22.6), "Haiti": (19.0, -72.7),
    "India": (22.9, 79.6), "Indonesia": (-2.2, 117.3), "Iran": (32.6, 54.3), "Iraq": (33.0, 43.7),
    "Ireland": (53.2, -8.1), "Israel": (31.4, 35.0), "Italy": (42.8, 12.6), "Japan": (36.6, 138.0),
    "Jordan": (31.3, 36.8), "Kenya": (0.5, 37.9), "Kuwait": (29.3, 47.6), "Lebanon": (33.9, 35.9),
    "Libya": (27.0, 18.0), "Malaysia": (4.0, 102.2), "Mali": (17.4, -3.5), "Mexico": (23.9, -102.5),
    "Moldova": (47.2, 28.5), "Morocco": (31.9, -6.3), "Mozambique": (-17.3, 35.5), "Myanmar": (21.1, 96.5),
    "Nepal": (28.2, 84.0), "Niger": (17.4, 9.4), "Nigeria": (9.6, 8.1), "North Korea": (40.2, 127.2),
    "Norway": (64.6, 12.7), "Oman": (20.6, 56.1), "Pakistan": (29.9, 69.3), "Palestine": (31.9, 35.2),
    "Peru": (-9.2, -74.4), "Philippines": (12.8, 122.9), "Poland": (52.1, 19.4), "Portugal": (39.6, -8.0),
    "Qatar": (25.3, 51.2), "Romania": (45.9, 25.0), "Russia": (61.5, 99.0), "Saudi Arabia": (24.0, 44.5),
    "Senegal": (14.4, -14.5), "Serbia": (44.2, 20.8), "Somalia": (6.1, 45.9), "South Africa": (-29.0, 25.1),
    "South Korea": (36.4, 127.8), "South Sudan": (7.3, 30.3), "Spain": (40.2, -3.6), "Sri Lanka": (7.6, 80.7),
    "Sudan": (15.6, 30.0), "Sweden": (62.8, 16.7), "Switzerland": (46.8, 8.2), "Syria": (35.0, 38.5),
    "Taiwan": (23.8, 121.0), "Thailand": (15.1, 101.0), "Tunisia": (34.1, 9.6), "Turkey": (39.1, 35.2),
    "Uganda": (1.3, 32.4), "Ukraine": (49.0, 31.4), "United Arab Emirates": (24.0, 54.3),
    "United Kingdom": (54.1, -2.9), "United States": (39.8, -98.6), "Venezuela": (7.1, -66.2),
    "Vietnam": (16.6, 106.3), "Yemen": (15.9, 47.6), "Zimbabwe": (-19.0, 29.9),
}


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    return 12742 * asin(sqrt(sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2))


def _merge_cities() -> tuple[dict[str, tuple[float, float, str]], dict[str, str]]:
    taken = {name.split(",")[0].casefold() for name in CURATED_CITY_POINTS} | set(CURATED_CITY_ALIASES)
    cities = dict(CURATED_CITY_POINTS)
    aliases = dict(CURATED_CITY_ALIASES)
    for name, (lat, lon, country) in natural_earth.CITY_POINTS.items():
        # A spelling variant of a curated city ("Kiev", "Rangoon") sits on top of it; keep the curated entry.
        if name.casefold() in taken or any(_distance_km((lat, lon), point[:2]) < 25 for point in CURATED_CITY_POINTS.values()):
            continue
        cities[name] = (lat, lon, country)
    for alias, name in natural_earth.CITY_ALIASES.items():
        if name in cities and alias not in taken and alias not in aliases:
            aliases[alias] = name
    return cities, aliases


CITY_POINTS, CITY_ALIASES = _merge_cities()
COUNTRY_POINTS: dict[str, tuple[float, float]] = {**natural_earth.COUNTRY_POINTS, **CURATED_COUNTRY_POINTS}
