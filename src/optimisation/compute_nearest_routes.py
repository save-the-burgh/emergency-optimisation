"""Create the two shortest service routes for every accident site."""

import argparse
import json
from pathlib import Path
from typing import Any

from route_helpers import create_geocoder, get_coords, get_route


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACCIDENTS = ROOT / "data/raw/accident-sites.json"
DEFAULT_SERVICES = ROOT / "data/raw/service-sites.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "nearest_routes.json"

def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data

def get_address(site: dict[str, Any]) -> str:
    address = site.get("full_address")
    if not isinstance(address, str) or not address.strip():
        raise ValueError(f"Site {site.get('id', '<unknown>')} has no full_address")
    return address


def geocode_sites(accidents: list[dict[str, Any]], services: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    geocode = create_geocoder()
    coordinates: dict[str, tuple[float, float]] = {}

    for site in [*accidents, *services]:
        site_id = site.get("id")
        if not isinstance(site_id, str):
            raise ValueError(f"Every site must have a string id: {site}")
        coordinates[site_id], _ = get_coords(geocode, get_address(site))
        print(f"Geocoded {site_id}")
    return coordinates


def build_routes(
    accidents: list[dict[str, Any]],
    services_by_category: dict[str, list[dict[str, Any]]],
    coordinates: dict[str, tuple[float, float]],
    top_n: int) -> dict[str, list[dict[str, Any]]]:

    output: dict[str, list[dict[str, Any]]] = {}

    for accident in accidents:
        accident_id = accident["id"]
        required_categories = accident.get("required_services", [])
        candidates = [
            (category, service)
            for category in required_categories
            for service in services_by_category.get(category, [])]
        if not candidates:
            raise ValueError(
                f"Accident {accident_id} has no service sites for "
                f"{required_categories}")

        routes = []
        for category, service in candidates:
            service_id = service["id"]
            distance_m, duration_s, _, geometry = get_route(
                coordinates[accident_id], coordinates[service_id])
            routes.append(
                {
                    "service_site_id": service_id,
                    "service_category": category,
                    "distance_m": distance_m,
                    "duration_s": duration_s,
                    "geometry": geometry} )

        output[accident_id] = sorted(
            routes, key=lambda route: (route["distance_m"], route["service_site_id"]))[:top_n]
        print(f"Selected {len(output[accident_id])} routes for {accident_id}")

    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find the shortest service routes for accident sites.")
    parser.add_argument("--accidents", type=Path, default=DEFAULT_ACCIDENTS)
    parser.add_argument("--services", type=Path, default=DEFAULT_SERVICES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top < 1:
        raise ValueError("--top must be at least 1")

    accident_data = load_json(args.accidents)
    service_data = load_json(args.services)
    accidents = accident_data.get("incident_sites")
    raw_services_by_category = service_data.get("service_sites")
    if not isinstance(accidents, list) or not isinstance(
        raw_services_by_category, dict):
        raise ValueError("Input files do not match the expected site schema")

    services = [
        service
        for category_services in raw_services_by_category.values()
        for service in category_services]
    services_by_category = {}
    for service in services:
        category = service.get("category")
        if not isinstance(category, str):
            raise ValueError(f"Service {service.get('id', '<unknown>')} has no category")
        services_by_category.setdefault(category, []).append(service)

    coordinates = geocode_sites(accidents, services)
    routes = build_routes(accidents, services_by_category, coordinates, args.top)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(routes, file, indent=2)
        file.write("\n")
    print(f"Saved routes to {args.output}")


if __name__ == "__main__":
    main()
