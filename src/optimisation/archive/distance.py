import sys
import ssl

import requests
import certifi
import geopy.geocoders

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic

# Create SSL context using certifi's certificates
ctx = ssl.create_default_context(cafile=certifi.where())
geopy.geocoders.options.default_ssl_context = ctx

geolocator = Nominatim(user_agent="my_app")
location = geolocator.geocode("Thomas Bayes Rd, Edinburgh EH9 3FG")
# print(location.latitude, location.longitude)

# Nominatim requires a descriptive user_agent (use your own name/app)
geolocator = Nominatim(user_agent="edinburgh-distance-script")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_coords(address):
    location = geocode(address)
    if location is None:
        raise ValueError(f"Could not find address: {address!r}")
    return (location.latitude, location.longitude), location.address


def driving_distance_m(origin, destination):
    """Driving distance in meters via the public OSRM server, or None on failure."""
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    )
    try:
        r = requests.get(url, params={"overview": "false"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "Ok":
            return None
        return data["routes"][0]["distance"]
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def main():
    if len(sys.argv) == 3:
        addr1, addr2 = sys.argv[1], sys.argv[2]
    else:
        addr1 = input("Address 1: ").strip()
        addr2 = input("Address 2: ").strip()

    try:
        coords1, resolved1 = get_coords(addr1)
        coords2, resolved2 = get_coords(addr2)
    except ValueError as e:
        print(e)
        sys.exit(1)

    print(f"\nFrom: {resolved1}")
    print(f"To:   {resolved2}\n")

    straight = geodesic(coords1, coords2)
    print(f"Straight-line distance: {straight.km:.2f} km ({straight.miles:.2f} miles)")

    driving = driving_distance_m(coords1, coords2)
    if driving is not None:
        print(f"Driving distance:       {driving / 1000:.2f} km ({driving / 1609.344:.2f} miles)")
    else:
        print("Driving distance:       unavailable (OSRM request failed)")


if __name__ == "__main__":
    main()