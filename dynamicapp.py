import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

from map_builder import build_dispatch_map
from data import (
    fetch_city_data,
    generate_random_accidents,
    calculate_distances,
    save_incident_data,
)
from city_loader import load_preloaded_cities
from optimizer import optimize_assignments

st.set_page_config(
    page_title="Dispatch Sim",
    layout="wide",
)
from auth import get_login_url, get_logout_url, get_current_user, logout

user = get_current_user()

st.title("Emergency Dispatch Simulator")

VEHICLE_TO_CATEGORY = {
    "Ambulances": "hospital",
    "Fire Engines": "fire",
    "Police Cars": "police",
}
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

st.sidebar.header("Account")
if user:
    st.sidebar.write(f"Logged in as **{user.get('name', user.get('email', 'User'))}**")
    if user.get("picture"):
        st.sidebar.image(user["picture"], width=50)
    if st.sidebar.button("Log out"):
        logout()
        st.markdown(f'<meta http-equiv="refresh" content="0; url={get_logout_url()}">', unsafe_allow_html=True)
        st.stop()
else:
    st.sidebar.markdown(f"[Log in with Auth0]({get_login_url()})")

# --- Sidebar: add a new city (the only feature that calls a live API) ---
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
                st.sidebar.success(f"Added {name}.")
            except Exception as exc:
                st.sidebar.error(
                    f"Could not add '{name}' right now. OpenStreetMap's services "
                    f"occasionally block automated requests. Try again shortly, "
                    f"or check the spelling. ({exc})"
                )

city_name = st.sidebar.selectbox("Select a city", sorted(st.session_state.cities.keys()))
city_data = st.session_state.cities[city_name]

all_centers = city_data["centers"]
hospitals = [c for c in all_centers if c["category"] == "hospital"]

raw_accidents = generate_random_accidents(bounds=city_data["bounds"], n=5, seed=42)
accidents = calculate_distances(hospitals, raw_accidents)
if save_jsons:
    output_path = save_incident_data(city_data["name"], accidents)
    st.sidebar.caption(f"Saved JSON: {output_path.name}")

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
    "hospital": st.sidebar.checkbox("hospital", value=True),
    "fire": st.sidebar.checkbox("fire", value=True),
    "police": st.sidebar.checkbox("police", value=True),
}

st.subheader("Overview")
kpi_col1, kpi_col2 = st.columns(2)

with kpi_col1:
    with st.container(border=True):
        st.metric("Emergency Centres", len(all_centers))

with kpi_col2:
    with st.container(border=True):
        st.metric("Vehicles Assigned", sum(city_fleet["assignments"].values()))

# --- Main content: Map / Fleet Assignment / Analytics ---
tab_map, tab_fleet, tab_analytics = st.tabs(["Map", "Fleet Assignment", "Analytics"])

with tab_map:
    map_center = (city_data["center"]["lat"], city_data["center"]["lon"])
    city_map = build_dispatch_map(
        all_centers, hospitals, accidents, selected_accident_id,
        visible_categories, center=map_center, assignments=city_fleet["assignments"],
    )
    st_folium(city_map, width=1200, height=700)

with tab_fleet:
    if not user:
        st.warning("Please log in with Auth0 to access vehicle assignment controls.")
        st.info("Only authenticated dispatchers are permitted to assign emergency vehicles.")
    else:
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

    st.subheader("Configure Capacities and Assign Vehicles")
    st.caption(
        "Set a Max Capacity per site, and either edit Assigned manually "
        "or use the optimizer button below."
    )

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
                "Max Capacity": city_fleet["capacities"].get(c["name"], c["capacity"]),
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

        st.progress(min(assigned_total / total, 1.0) if total > 0 else 0.0)

        if remaining < 0:
            st.error(f"Over-assigned by {abs(remaining)} {vehicle_type.lower()}.")
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
                c["name"]: city_fleet["capacities"].get(c["name"], c["capacity"])
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

with tab_analytics:
    st.subheader("Vehicle Distribution by Center")

    if city_fleet["assignments"]:
        fig = px.bar(
            x=list(city_fleet["assignments"].keys()),
            y=list(city_fleet["assignments"].values()),
            labels={"x": "Center", "y": "Vehicles Assigned"},
            title="Current Vehicle Allocation",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run the optimizer or manually assign vehicles to see this chart.")

    st.subheader("Accident Distances to Nearest Hospital")
    if accidents:
        dist_df = pd.DataFrame([
            {"Accident": a["id"], "Nearest Hospital (km)": a["distances"][0]["distance_km"]}
            for a in accidents
            if a["distances"]
        ])
        fig2 = px.bar(
            dist_df,
            x="Accident",
            y="Nearest Hospital (km)",
            title="Distance to Nearest Hospital per Accident",
        )
        st.plotly_chart(fig2, use_container_width=True)
