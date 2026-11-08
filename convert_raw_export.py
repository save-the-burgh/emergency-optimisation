import json
from pathlib import Path
from data import _parse_osm_elements  # reuse your existing parsing logic

RAW_DIR = Path(__file__).parent / "city_data"

OUTPUT_DIR = Path(__file__).parent / "city_data"
OUTPUT_DIR.mkdir(exist_ok=True)

CITIES = {
    "edinburgh": {
        "center": {"lat": 55.9533, "lon": -3.1883},
        "bounds": {"lat_min": 55.90, "lat_max": 55.97, "lon_min": -3.30, "lon_max": -3.10},
    },
    "cork": {
        "center": {"lat": 51.8985, "lon": -8.4756},
        "bounds": {"lat_min": 51.85, "lat_max": 51.95, "lon_min": -8.55, "lon_max": -8.40},
    },
    "colchester": {
        "center": {"lat": 51.8959, "lon": 0.8919},
        "bounds": {"lat_min": 51.85, "lat_max": 51.95, "lon_min": 0.85, "lon_max": 0.95},
    },
}

for city_key, info in CITIES.items():
    raw_path = RAW_DIR / f"{city_key}_raw.json"
    if not raw_path.exists():
        print(f"Skipping {city_key} — {raw_path} not found")
        continue

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    centers = _parse_osm_elements(raw["elements"])

    data = {
        "name": city_key.capitalize(),
        "center": info["center"],
        "bounds": info["bounds"],
        "centers": centers,
    }

    out_path = OUTPUT_DIR / f"{city_key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"{city_key}: saved {len(centers)} centers to {out_path}")
