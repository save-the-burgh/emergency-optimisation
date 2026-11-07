"""Shared geocoding and routing helpers."""

import ssl
from typing import Any

import certifi
import geopy.geocoders
import requests
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim


geopy.geocoders.options.default_ssl_context = ssl.create_default_context(
    cafile=certifi.where()
)


def create_geocoder(user_agent: str = "emergency-optimisation-routes") -> RateLimiter:
    geolocator = Nominatim(user_agent=user_agent)
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)


def get_coords(geocode: RateLimiter, address: str) -> tuple[tuple[float, float], str]:
    location = geocode(address)
    if location is None:
        raise ValueError(f"Could not find address: {address!r}")
    return (location.latitude, location.longitude), location.address


def get_route(
    origin: tuple[float, float], destination: tuple[float, float]
) -> tuple[float, float, list[tuple[float, float]], dict[str, Any]]:
    """Return distance, duration, a folium path, and GeoJSON geometry."""
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    )
    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise RuntimeError(f"Routing request failed: {error}") from error

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"OSRM could not route between sites: {data}")

    route = data["routes"][0]
    geometry = route["geometry"]
    path = [(lat, lon) for lon, lat in geometry["coordinates"]]
    return route["distance"], route["duration"], path, geometry
