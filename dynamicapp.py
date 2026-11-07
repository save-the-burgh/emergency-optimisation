import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

from map_builder import build_dispatch_map
from data import fetch_city_data, generate_random_accidents, calculate_distances
from city_loader import load_preloaded_cities
from optimizer import optimize_assignments

st.set_page_config(
    page_title = "Save the Burgh",
    page_icon="assets/capy.png",
    layout="wide")
st.title("Emergency Dispatch Map")

VEHICLE_TO_CATEGORY = {
    "Ambulances": "Hospitals",
    "Fire Engines": "Fire Stations",
    "Police Cars": "Police Stations",
}
DEFAULT_CAPACITY = 5

# --- Load preloaded cities once per session (no API calls) ---
if "cities" not in st.session_state:
    cities, skipped_files = load_preloaded_cities()
    st.session_state.cities = cities

    for filename, reason in skipped_files:
        st.sidebar.warning(f"Skipped {filename}: {reason}")

if "fleet" not in st.session_state:
    st.session_state.fleet = {}

if "fleet_version" not in st.session_state:
    st.session_state.fleet_version = 0

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

# --- Initialize fleet state for this city (totals, capacities, assignments) ---
if city_name not in st.session_state.fleet:
    st.session_state.fleet[city_name] = {
        "totals": {"Ambulances": 10, "Fire Engines": 8, "Police Cars": 12},
        "capacities": {},
        "assignments": {},
    }

city_fleet = st.session_state.fleet[city_name]

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
    visible_categories, center=map_center, assignments=city_fleet["assignments"],
)
st_folium(city_map, width=1200, height=700)

# --- Vehicle fleet management (below the map) ---
st.header("Vehicle Fleet & Assignment")

st.subheader("Total Fleet Size")
cols = st.columns(3)
for col, vehicle_type in zip(cols, VEHICLE_TO_CATEGORY):
    with col:
        city_fleet["totals"][vehicle_type] = st.number_input(
            vehicle_type,
            min_value=0,
            value=city_fleet["totals"][vehicle_type],
            step=1,
            key=f"total_{city_name}_{vehicle_type}",
        )

st.subheader("Configure Capacities & Assign Vehicles")
st.caption("Set a Max Capacity per site, and either edit Assigned manually or use the optimizer button below.")

for vehicle_type, category in VEHICLE_TO_CATEGORY.items():
    matching_centers = [c for c in all_centers if c["category"] == category]
    total = city_fleet["totals"][vehicle_type]

    st.markdown(f"**{vehicle_type}** — total available: {total}")

    if not matching_centers:
        st.caption(f"No {category.lower()} found in {city_name}.")
        continue

    table_rows = [
        {
            "Center": c["name"],
            "Max Capacity": city_fleet["capacities"].get(c["name"], DEFAULT_CAPACITY),
            "Assigned": city_fleet["assignments"].get(c["name"], 0),
        }
        for c in matching_centers
    ]
    df = pd.DataFrame(table_rows)

    editor_key = f"editor_{city_name}_{vehicle_type}_{st.session_state.fleet_version}"
    edited_df = st.data_editor(
        df,
        column_config={
            "Center": st.column_config.TextColumn(disabled=True),
            "Max Capacity": st.column_config.NumberColumn(min_value=0, step=1),
            "Assigned": st.column_config.NumberColumn(min_value=0, step=1),
        },
        hide_index=True,
        key=editor_key,
    )

    for _, row in edited_df.iterrows():
        city_fleet["capacities"][row["Center"]] = int(row["Max Capacity"])
        city_fleet["assignments"][row["Center"]] = int(row["Assigned"])

    assigned_total = int(edited_df["Assigned"].sum())
    remaining = total - assigned_total
    if remaining < 0:
        st.error(f"Over-assigned by {abs(remaining)} {vehicle_type.lower()}!")
    else:
        st.caption(f"{assigned_total}/{total} assigned — {remaining} remaining")

    st.divider()

st.subheader("Automatic Assignment")
st.caption(
    "Currently assigns vehicles randomly, respecting each center's Max Capacity, "
    "as a placeholder. This will be replaced with the real optimizer, which will "
    "use historical accident data instead of random choice."
)

if st.button("Run Optimizer (Random Placeholder)"):
    for vehicle_type, category in VEHICLE_TO_CATEGORY.items():
        matching_centers = [c for c in all_centers if c["category"] == category]
        total = city_fleet["totals"][vehicle_type]
        capacities = {
            c["name"]: city_fleet["capacities"].get(c["name"], DEFAULT_CAPACITY)
            for c in matching_centers
        }

        eligible_count = sum(1 for cap in capacities.values() if cap > 0)
        if total < eligible_count:
            st.warning(
                f"Only {total} {vehicle_type.lower()} available for {eligible_count} "
                f"{category.lower()} — not every site could get the guaranteed minimum of 1."
            )

        result = optimize_assignments(
            centers=matching_centers,
            total_vehicles=total,
            capacities=capacities,
        )

        for c in matching_centers:
            city_fleet["assignments"][c["name"]] = result.get(c["name"], 0)

        leftover = total - sum(result.values())
        if leftover > 0:
            st.warning(
                f"Could not place {leftover} {vehicle_type.lower()} — "
                f"total capacity across all {category.lower()} is full."
            )

    st.session_state.fleet_version += 1
    st.rerun()
