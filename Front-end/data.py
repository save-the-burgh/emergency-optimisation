import random
import hashlib
import json
from pathlib import Path
import requests
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
    "hospital": "hospital",
    "fire_station": "fire",
    "police": "police",
}

LEGACY_CATEGORY_MAP = {
    "hospitals": "hospital",
    "fire stations": "fire",
    "fire_station": "fire",
    "police stations": "police",
}

LARGE_HOSPITAL_MARKERS = (
    "general hospital",
    "infirmary",
    "royal hospital",
    "western general",
)

SERVICE_CATEGORY_LABELS = {
    "hospital": "Hospital",
    "fire": "Fire Station",
    "police": "Police Station",
}


_geolocator = Nominatim(user_agent=HEADERS["User-Agent"])
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1)


def add_service_site_metadata(site, site_number):
    """Assign a per-city site ID and deterministic estimated incident capacity."""
    category = site["category"].strip().casefold()
    category = LEGACY_CATEGORY_MAP.get(category, category)
    if category not in {"hospital", "fire", "police"}:
        raise ValueError(f"Unknown service site category: {site['category']}")
    site["category"] = category

    identity = "\0".join((
        category,
        site["name"].strip().casefold(),
        f"{float(site['lat']):.7f}",
        f"{float(site['lon']):.7f}",
    ))
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    site["index"] = f"S{site_number}"

    if "capacity" not in site:
        if category == "hospital":
            name = site["name"].casefold()
            minimum, maximum = (
                (30, 60)
                if any(marker in name for marker in LARGE_HOSPITAL_MARKERS)
                else (12, 30)
            )
        elif category == "fire":
            minimum, maximum = 2, 4
        elif category == "police":
            minimum, maximum = 3, 8
        site["capacity"] = random.Random(int(identity_hash[:16], 16)).randint(
            minimum, maximum
        )

    return site


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

        fallback_names = {
            "hospital": "Unnamed hospital",
            "fire": "Unnamed fire station",
            "police": "Unnamed police station",
        }
        name = tags.get("name") or fallback_names[category]
        centers.append(add_service_site_metadata({
            "name": name,
            "lat": lat,
            "lon": lon,
            "category": category,
        }, site_number=len(centers) + 1))

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
    categories = ["police", "fire", "hospital"]
    random.shuffle(categories)
    for i in range(n):
        lat = random.uniform(bounds["lat_min"], bounds["lat_max"])
        lon = random.uniform(bounds["lon_min"], bounds["lon_max"])
        cat = categories[i] if i < len(categories) else random.choice(categories)
        accidents.append({"id": f"A{i+1}", "lat": lat, "lon": lon, "category": cat})
    return accidents


def save_incident_data(city_name, incidents):
    """Save generated incidents and their distances under the incident_sites key."""
    filename = "".join(
        character if character.isalnum() or character in "-_ " else "_"
        for character in city_name).strip().replace(" ", "_")
    if not filename:
        raise ValueError("city_name must contain at least one valid filename character")

    output_path = Path(__file__).parent / "incidence_data" / f"{filename}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"incident_sites": incidents}, indent=2),
        encoding="utf-8")
    return output_path


def calculate_distances(service_sites, accidents):
    """Add ordered driving distances to sites matching each incident category."""
    enriched = []
    for a in accidents:
        category = a["category"]
        if category not in SERVICE_CATEGORY_LABELS:
            raise ValueError(f"Unknown incident category: {category}")

        distances = []
        matching_sites = [
            site for site in service_sites if site["category"] == category
        ]
        for site in matching_sites:
            coordinates = f"{a['lon']},{a['lat']};{site['lon']},{site['lat']}"
            response = requests.get(
                f"https://router.project-osrm.org/route/v1/driving/{coordinates}",
                params={"overview": "false"},
                timeout=30,
            )
            response.raise_for_status()
            routes = response.json().get("routes", [])
            if not routes:
                raise RuntimeError(
                    f"No driving route found from incident {a['id']} "
                    f"to {site['name']}"
                )
            km = routes[0]["distance"] / 1000
            distances.append({
                "index": site["index"],
                "service_site": site["name"],
                "category": category,
                "capacity": site["capacity"],
                "distance_km": round(km, 2),
            })
        distances.sort(key=lambda d: d["distance_km"])

        a_copy = dict(a)
        a_copy["distances"] = distances
        enriched.append(a_copy)

    return enriched
