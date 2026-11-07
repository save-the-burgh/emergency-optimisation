import streamlit as st
from streamlit_folium import st_folium

from map_builder import build_dispatch_map
from data import get_hospitals, generate_random_accidents, calculate_distances

st.set_page_config(layout="wide")
st.title("Edinburgh Emergency Dispatch Map")

hospitals = get_hospitals()
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

# --- Main panel: ---
city_map = build_dispatch_map(hospitals, accidents, selected_accident_id)
st_folium(city_map, width=1200, height=700)
