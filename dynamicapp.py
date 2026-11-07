import streamlit as st
from streamlit_folium import st_folium

from map_builder import build_dispatch_map
from data import fetch_city_data, generate_random_accidents, calculate_distances
from city_loader import load_preloaded_cities

st.set_page_config(layout="wide")
st.title("Emergency Dispatch Map")

# Load the 3 preloaded cities once per session, from local JSON files.
if "cities" not in st.session_state:
    cities, skipped_files = load_preloaded_cities()
    st.session_state.cities = cities

    for filename, reason in skipped_files:
        st.sidebar.warning(f"Skipped {filename}: {reason}")

# --- Add a new city (the only feature that calls a live API) ---
st.sidebar.header("Cities")
with st.sidebar.form("add_city_form", clear_on_submit=True):
    new_city_name = st.text_input("Add a new city")
    submitted = st.form_submit_button("Add City")

if submitted and new_city_name.strip():
    name = new_city_name.strip()
    if name in st.session_state.cities:
        st.sidebar.info(f"{name} is already loaded.")
    else:
        with st.spinner(f"Fetching data for {name}..."):
            try:
                st.session_state.cities[name] = fetch_city_data(name)
                st.sidebar.success(f"Added {name}!")
            except Exception as exc:
                st.sidebar.error(
                    f"Could not add '{name}' right now. OpenStreetMap's services "
                    f"occasionally block automated requests. Try again shortly, "
                    f"or check the spelling. ({exc})"
                )

city_name = st.sidebar.selectbox("Select a city", sorted(st.session_state.cities.keys()))
city_data = st.session_state.cities[city_name]

all_centers = city_data["centers"]
hospitals = [c for c in all_centers if c["category"] == "Hospitals"]

raw_accidents = generate_random_accidents(bounds=city_data["bounds"], n=5, seed=42)
accidents = calculate_distances(hospitals, raw_accidents)

# --- Sidebar: distances above controls ---
distance_section = st.sidebar.empty()

st.sidebar.header("Controls")
selected_accident_id = st.sidebar.selectbox(
    "Select an accident to view distances",
    [a["id"] for a in accidents],
)

selected = next(a for a in accidents if a["id"] == selected_accident_id)

with distance_section.container():
    st.subheader(f"Distances from Accident {selected['id']}")
    if hospitals:
        st.table([
            {"Hospital": d["hospital"], "Distance (km)": d["distance_km"]}
            for d in selected["distances"]
        ])
    else:
        st.warning("No hospitals found for this city.")

# --- Map layer toggles ---
st.sidebar.header("Map Layers")
visible_categories = {
    "Hospitals": st.sidebar.checkbox("Hospitals", value=True),
    "Fire Stations": st.sidebar.checkbox("Fire Stations", value=True),
    "Police Stations": st.sidebar.checkbox("Police Stations", value=True),
}

# --- Main panel: map ---
map_center = (city_data["center"]["lat"], city_data["center"]["lon"])
city_map = build_dispatch_map(
    all_centers, hospitals, accidents, selected_accident_id,
    visible_categories, center=map_center,
)
st_folium(city_map, width=1200, height=700)

if "cities" not in st.session_state:
    cities, skipped_files = load_preloaded_cities()
    st.session_state.cities = cities

    for filename, reason in skipped_files:
        st.sidebar.warning(f"Skipped {filename}: {reason}")
