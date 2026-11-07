import folium

EDINBURGH_CENTER = (55.9533, -3.1883)

def distance_color(km, max_km=10):
 
    ratio = min(km / max_km, 1.0)
    red = int(255 * ratio)
    green = int(255 * (1 - ratio))
    return f"#{red:02x}{green:02x}00"

def build_dispatch_map(hospitals, accidents, selected_accident_id,
                        center=EDINBURGH_CENTER, zoom=12):
 
    city_map = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    for h in hospitals:
        folium.Marker(
            location=[h["lat"], h["lon"]],
            popup=h["name"],
            icon=folium.Icon(color="red", icon="plus-sign"),
        ).add_to(city_map)

    for a in accidents:
        is_selected = (a["id"] == selected_accident_id)

        folium.Marker(
            location=[a["lat"], a["lon"]],
            popup=f"Accident {a['id']}",
            icon=folium.Icon(
                color="blue" if not is_selected else "purple",
                icon="info-sign",
            ),
        ).add_to(city_map)

        if not is_selected:
            continue  # only draw lines for the selected accident

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
