import random
import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

HEADERS = {
    "User-Agent": "EdinburghDispatchSim/1.0 (student project; contact: your-email@example.com)"
}

AMENITY_CATEGORY_MAP = {
    "hospital": "Hospitals",
    "fire_station": "Fire Stations",
    "police": "Police Stations",
}

_geolocator = Nominatim(user_agent=HEADERS["User-Agent"])
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1)


def geocode_city(city_name):
    """Turn a city name into a center point + bounding box via Nominatim."""
    location = _geocode(city_name, exactly_one=True)

    if location is None:
        raise ValueError(f"Could not find a location for '{city_name}'")

    bbox = location.raw.get("boundingbox")
    if not bbox:
        raise ValueError(f"No bounding box returned for '{city_name}'")

    south, north, west, east = map(float, bbox)

    return {
        "center": {"lat": location.latitude, "lon": location.longitude},
        "bounds": {"lat_min": south, "lat_max": north, "lon_min": west, "lon_max": east},
    }


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


def fetch_emergency_centers(bbox):
    """Query Overpass for hospitals/fire/police within a given bbox string."""
    query = _build_overpass_query(bbox)
    errors = []

    for url in OVERPASS_URLS:
        try:
            response = requests.get(url, params={"data": query}, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return _parse_osm_elements(response.json()["elements"])
        except requests.RequestException as exc:
            errors.append(f"{url} -> {exc}")

    raise RuntimeError("All Overpass mirrors failed:\n" + "\n".join(errors))


def fetch_city_data(city_name):
    """
    Full pipeline for a NEW city (not one of the 3 preloaded ones):
    name -> geocode -> fetch emergency centers.
    Used only by the "Add City" button in app.py.
    """
    geo = geocode_city(city_name)
    b = geo["bounds"]
    bbox = f"{b['lat_min']},{b['lon_min']},{b['lat_max']},{b['lon_max']}"

    centers = fetch_emergency_centers(bbox)

    return {
        "name": city_name,
        "center": geo["center"],
        "bounds": geo["bounds"],
        "centers": centers,
    }


def generate_random_accidents(bounds, n=5, seed=None):
    """Generate n random accident locations within a city's bounding box."""
    if seed is not None:
        random.seed(seed)

    accidents = []
    for i in range(n):
        lat = random.uniform(bounds["lat_min"], bounds["lat_max"])
        lon = random.uniform(bounds["lon_min"], bounds["lon_max"])
        accidents.append({"id": f"A{i+1}", "lat": lat, "lon": lon})
    return accidents


def calculate_distances(hospitals, accidents):
    """
    PLACEHOLDER — replace with your teammate's real distance-calculation
    module once ready. Must return the same shape of data.
    """
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
