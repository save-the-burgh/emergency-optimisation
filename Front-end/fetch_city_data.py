import json
from pathlib import Path
from data import fetch_emergency_centers

# Approximate bounding boxes (south, west, north, east).
# Double-check these against a mapping tool if precision matters.
KNOWN_CITIES = {
    "Edinburgh": {
        "center": {"lat": 55.9533, "lon": -3.1883},
        "bounds": {"lat_min": 55.90, "lat_max": 55.97, "lon_min": -3.30, "lon_max": -3.10},
    },
    "Cork": {
        "center": {"lat": 51.8985, "lon": -8.4756},
        "bounds": {"lat_min": 51.85, "lat_max": 51.95, "lon_min": -8.55, "lon_max": -8.40},
    },
    "Colchester": {
        "center": {"lat": 51.8959, "lon": 0.8919},
        "bounds": {"lat_min": 51.85, "lat_max": 51.95, "lon_min": 0.85, "lon_max": 0.95},
    },
}

OUTPUT_DIR = Path(__file__).parent / "city_data"
OUTPUT_DIR.mkdir(exist_ok=True)

for city_name, info in KNOWN_CITIES.items():
    print(f"Fetching {city_name}...")
    b = info["bounds"]
    bbox = f"{b['lat_min']},{b['lon_min']},{b['lat_max']},{b['lon_max']}"

    try:
        centers = fetch_emergency_centers(bbox)
        data = {
            "name": city_name,
            "center": info["center"],
            "bounds": info["bounds"],
            "centers": centers,
        }
        out_path = OUTPUT_DIR / f"{city_name.lower()}.json"
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Saved {len(centers)} centers to {out_path}")
    except Exception as exc:
        print(f"  FAILED for {city_name}: {exc}")
