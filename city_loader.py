import json
from pathlib import Path

CITY_DATA_DIR = Path(__file__).parent / "city_data"
REQUIRED_KEYS = {"name", "center", "bounds", "centers"}

def load_preloaded_cities():
    """
    Load the pre-fetched, processed JSON files for the main cities.
    Skips raw exports or malformed files instead of crashing.
    """
    cities = {}
    skipped = []

    for file in CITY_DATA_DIR.glob("*.json"):
        if file.stem.endswith("_raw"):
            continue  # ignore raw Overpass exports if any end up here

        with open(file, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                skipped.append((file.name, "invalid JSON"))
                continue

        missing = REQUIRED_KEYS - data.keys()
        if missing:
            skipped.append((file.name, f"missing keys: {missing}"))
            continue

        cities[data["name"]] = data

    return cities, skipped
