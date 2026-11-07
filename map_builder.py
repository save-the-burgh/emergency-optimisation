import folium

EDINBURGH_CENTER = (55.9533, -3.1883)

CATEGORY_STYLE = {
    "Hospitals":      {"color": "red",       "icon": "plus-sign", "prefix": "glyphicon"},
    "Fire Stations":  {"color": "orange",    "icon": "fire",      "prefix": "fa"},
    "Police Stations":{"color": "cadetblue", "icon": "shield",    "prefix": "fa"},
}

def distance_color(km, max_km=10):
    ratio = min(km / max_km, 1.0)
    red = int(255 * ratio)
    green = int(255 * (1 - ratio))
    return f"#{red:02x}{green:02x}00"

def build_dispatch_map(centers, hospitals, accidents, selected_accident_id,
                        visible_categories, center=EDINBURGH_CENTER, zoom=12):
    city_map = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    # Draw emergency centers — only the categories ticked on in the sidebar
    for c in centers:
        if not visible_categories.get(c["category"], False):
            continue

        style = CATEGORY_STYLE.get(
            c["category"], {"color": "gray", "icon": "info-sign", "prefix": "glyphicon"}
        )
        folium.Marker(
            location=[c["lat"], c["lon"]],
            popup=f"{c['name']} ({c['category']})",
            icon=folium.Icon(color=style["color"], icon=style["icon"], prefix=style["prefix"]),
        ).add_to(city_map)

    # Accidents + distance lines to hospitals (same logic as before)
    for a in accidents:
        is_selected = (a["id"] == selected_accident_id)

        folium.Marker(
            location=[a["lat"], a["lon"]],
            popup=f"Accident {a['id']}",
            icon=folium.Icon(color="purple" if is_selected else "blue", icon="info-sign"),
        ).add_to(city_map)

        if not is_selected:
            continue

        for i, d in enumerate(a["distances"]):
            hosp = hospitals[d["hospital_index"]]
            is_nearest = (i == 0)
            folium.PolyLine(
                locations=[[a["lat"], a["lon"]], [hosp["lat"], hosp["lon"]]],
                color=distance_color(d["distance_km"]),
                weight=5 if is_nearest else 3,
                opacity=1.0 if is_nearest else 0.6,
                tooltip=f"{a['id']} → {hosp['name']}: {d['distance_km']} km",
            ).add_to(city_map)

    return city_map
