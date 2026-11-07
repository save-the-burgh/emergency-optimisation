import random
import requests
from geopy.distance import geodesic

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
EDINBURGH_BBOX = "55.90,-3.30,55.97,-3.10"  # south,west,north,east

AMENITY_CATEGORY_MAP = {
    "hospital": "Hospitals",
    "fire_station": "Fire Stations",
    "police": "Police Stations",
}

# --- Fallback data used if OpenStreetMap is unreachable ---
# NOTE: Verify these against official sources before using beyond a prototype.
FALLBACK_CENTERS = [
    # Hospitals
    {"name": "Royal Infirmary of Edinburgh", "lat": 55.9220, "lon": -3.1338, "category": "Hospitals"},
    {"name": "Western General Hospital",     "lat": 55.9649, "lon": -3.2210, "category": "Hospitals"},
    {"name": "Royal Edinburgh Hospital",     "lat": 55.9254, "lon": -3.2209, "category": "Hospitals"},
    {"name": "Astley Ainslie Hospital",      "lat": 55.9316, "lon": -3.2075, "category": "Hospitals"},
    {"name": "Liberton Hospital",            "lat": 55.9196, "lon": -3.1584, "category": "Hospitals"},

    # Fire Stations
    {"name": "McDonald Road Fire Station",   "lat": 55.9637, "lon": -3.1844, "category": "Fire Stations"},
    {"name": "Tollcross Fire Station",       "lat": 55.9427, "lon": -3.2042, "category": "Fire Stations"},
    {"name": "Liberton Fire Station",        "lat": 55.9117, "lon": -3.1623, "category": "Fire Stations"},
    {"name": "Crewe Toll Fire Station",      "lat": 55.9721, "lon": -3.2252, "category": "Fire Stations"},
    {"name": "Marionville Fire Station",     "lat": 55.9567, "lon": -3.1503, "category": "Fire Stations"},

    # Police Stations
    {"name": "St Leonard's Police Station",  "lat": 55.9429, "lon": -3.1810, "category": "Police Stations"},
    {"name": "Gayfield Square Police Station","lat": 55.9578, "lon": -3.1839, "category": "Police Stations"},
    {"name": "Corstorphine Police Station",  "lat": 55.9423, "lon": -3.2745, "category": "Police Stations"},
    {"name": "Drylaw Police Station",        "lat": 55.9680, "lon": -3.2418, "category": "Police Stations"},
    {"name": "Wester Hailes Police Station", "lat": 55.9219, "lon": -3.2920, "category": "Police Stations"},
]


def _build_overpass_query(bbox):
    clauses = []
    for amenity in AMENITY_CATEGORY_MAP:
        clauses.append(f'node["amenity"="{amenity}"]({bbox});')
        clauses.append(f'way["amenity"="{amenity}"]({bbox});')
        clauses.append(f'relation["amenity"="{amenity}"]({bbox});')
    return f"""
    [out:json][timeout:25];
    (
      {" ".join(clauses)}
    );
    out center tags;
    """


def _parse_osm_elements(elements):
    centers = []
    for el in elements:
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        category = AMENITY_CATEGORY_MAP.get(amenity)
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        if not (category and lat and lon):
            continue

        name = tags.get("name") or f"Unnamed {category[:-1]}"
        centers.append({"name": name, "lat": lat, "lon": lon, "category": category})

    return centers


HEADERS = {
    "User-Agent": "HackathonSim1.0 (student project; contact: your-email@example.com)"
}

def fetch_emergency_centers(bbox=EDINBURGH_BBOX):
    """
    Query OpenStreetMap (via Overpass API) for hospitals, fire stations,
    and police stations. Tries multiple mirrors before giving up.

    Raises requests.RequestException if every mirror fails — the caller
    decides how to handle that (e.g. fall back to FALLBACK_CENTERS).
    """
    query = _build_overpass_query(bbox)
    last_error = None

    for url in OVERPASS_URLS:
        try:
            response = requests.get(url, params={"data": query}, timeout=30)
            response.raise_for_status()
            elements = response.json()["elements"]
            return _parse_osm_elements(elements)
        except requests.RequestException as exc:
            last_error = exc
            continue

    raise last_error


EDINBURGH_BOUNDS = {
    "lat_min": 55.90, "lat_max": 55.97,
    "lon_min": -3.30, "lon_max": -3.10,
}

def generate_random_accidents(n=5, seed=None):
    if seed is not None:
        random.seed(seed)

    accidents = []
    for i in range(n):
        lat = random.uniform(EDINBURGH_BOUNDS["lat_min"], EDINBURGH_BOUNDS["lat_max"])
        lon = random.uniform(EDINBURGH_BOUNDS["lon_min"], EDINBURGH_BOUNDS["lon_max"])
        accidents.append({"id": f"A{i+1}", "lat": lat, "lon": lon})
    return accidents

def calculate_distances(hospitals, accidents):
    enriched = []
    for a in accidents:
        distances = []
        for idx, h in enumerate(hospitals):
            km = geodesic((a["lat"], a["lon"]), (h["lat"], h["lon"])).km
            distances.append({
                "hospital_index": idx,
                "hospital": h["name"],
                "distance_km": round(km, 2),
            })
        distances.sort(key=lambda d: d["distance_km"])

        a_copy = dict(a)
        a_copy["distances"] = distances
        enriched.append(a_copy)

    return enriched
