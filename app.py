import streamlit as st
import requests
from streamlit_folium import st_folium

from map_builder import build_dispatch_map
from data import fetch_emergency_centers, FALLBACK_CENTERS, generate_random_accidents, calculate_distances

st.set_page_config(layout="wide")
st.title("Edinburgh Emergency Dispatch Map")

@st.cache_data(ttl=3600)  # re-query OSM at most once per hour
def get_emergency_centers():
    try:
        return fetch_emergency_centers()
    except requests.RequestException as error:
        st.warning(f"Could not reach OpenStreetMap — showing fallback hospital data only.Error is{error}")
        return FALLBACK_CENTERS

with st.spinner("Loading emergency center locations from OpenStreetMap..."):
    all_centers = get_emergency_centers()

hospitals = [c for c in all_centers if c["category"] == "Hospitals"]

raw_accidents = generate_random_accidents(n=5, seed=42)
accidents = calculate_distances(hospitals, raw_accidents)

# --- Sidebar layout ---
st.sidebar.title("Dispatch Panel")

distance_section = st.sidebar.empty()

st.sidebar.header("Controls")
selected_accident_id = st.sidebar.selectbox(
    "Select an accident to view distances",
    [a["id"] for a in accidents],
)

selected = next(a for a in accidents if a["id"] == selected_accident_id)

with distance_section.container():
    st.subheader(f"Distances from Accident {selected['id']}")
    st.table([
        {"Hospital": d["hospital"], "Distance (km)": d["distance_km"]}
        for d in selected["distances"]
    ])

# --- NEW: checkboxes + auto-generated lists ---
st.sidebar.header("Map Layers")
visible_categories = {
    "Hospitals": st.sidebar.checkbox("Hospitals", value=True),
    "Fire Stations": st.sidebar.checkbox("Fire Stations", value=True),
    "Police Stations": st.sidebar.checkbox("Police Stations", value=True),
}

for category, is_visible in visible_categories.items():
    matching = [c["name"] for c in all_centers if c["category"] == category]
    label = f"{category} ({len(matching)})"
    if is_visible:
        with st.sidebar.expander(label):
            for name in matching:
                st.write(f"- {name}")
    else:
        st.sidebar.caption(f"{label} — hidden")

# --- Main panel ---
city_map = build_dispatch_map(all_centers, hospitals, accidents, selected_accident_id, visible_categories)
st_folium(city_map, width=1200, height=700)
