import sys
import json
import folium
from geopy.distance import geodesic

from route_helpers import create_geocoder, get_coords, get_route


def main():
    if len(sys.argv) == 3:
        addr1, addr2 = sys.argv[1], sys.argv[2]
    else:
        addr1 = input("Address 1: ").strip()
        addr2 = input("Address 2: ").strip()

    geocode = create_geocoder("edinburgh-route-script")
    coords1, resolved1 = get_coords(geocode, addr1)
    coords2, resolved2 = get_coords(geocode, addr2)
    print(f"From: {resolved1}\nTo:   {resolved2}\n")

    straight_km = geodesic(coords1, coords2).km
    dist_m, dur_s, path, geometry = get_route(coords1, coords2)

    print(f"Straight-line: {straight_km:.2f} km")
    print(f"Driving:       {dist_m / 1000:.2f} km, about {dur_s / 60:.0f} min")
    print(f"Path has {len(path)} points")

    # 1. Save as GeoJSON (works in QGIS, geojson.io, Leaflet, Mapbox, etc.)
    feature = {
        "type": "Feature",
        "properties": {"from": resolved1, "to": resolved2, "distance_m": dist_m},
        "geometry": geometry,
    }
    with open("route.geojson", "w") as f:
        json.dump(feature, f)

    # 2. Build an interactive map
    m = folium.Map(location=coords1, zoom_start=13)
    folium.Marker(coords1, popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(coords2, popup="End", icon=folium.Icon(color="red")).add_to(m)
    folium.PolyLine(path, weight=5, color="blue", opacity=0.8).add_to(m)
    m.fit_bounds(path)
    m.save("route_map.html")

    print("\nSaved route.geojson and route_map.html (open the HTML file in a browser)")


if __name__ == "__main__":
    main()