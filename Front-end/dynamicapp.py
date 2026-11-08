import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import folium_static

from map_builder import build_dispatch_map
from data import (
    SERVICE_CATEGORY_LABELS,
    fetch_city_data,
    generate_random_accidents,
    calculate_distances,
    save_incident_data,
)
from city_loader import load_preloaded_cities
from model import LP_Optimiser, optimize_fleet_allocation
from optimizer import random_assignments
from benchmark import (
    compare_assignments,
    generate_hotspot_incidents,
    nearest_center_baseline,
    stress_test,
)

st.set_page_config(
    page_title="Dispatch Sim",
    layout="wide",
)
from auth import get_login_url, get_logout_url, get_current_user, logout
N_INCIDENTS=10
save_jsons = True
user = get_current_user()

# st.title("Save the Burgh")
st.markdown(
    "<h1 style='text-align: center;'>Save the Burgh</h1>",
    unsafe_allow_html=True,
)

VEHICLE_TO_CATEGORY = {
    "Ambulances": "hospital",
    "Fire Engines": "fire",
    "Police Cars": "police",
}


def run_distance_optimiser(incidents, centers):
    """Solve each incident category and combine its optimal results."""
    total_distance = 0.0
    assignments = []
    for category in VEHICLE_TO_CATEGORY.values():
        category_incidents = [
            incident for incident in incidents if incident["category"] == category
        ]
        if not category_incidents:
            continue
        result = LP_Optimiser(
            centers=[center for center in centers if center["category"] == category],
            incidents=category_incidents,
            return_details=True,
            verbose=False,
        )
        if result is None:
            return None
        total_distance += result["total_km"]
        assignments.extend(result["rows"])
    return {"total_km": total_distance, "rows": assignments}


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

if "fleet_assignment_feedback" not in st.session_state:
    st.session_state.fleet_assignment_feedback = {}

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

city_name = st.sidebar.selectbox("Select a city", sorted(st.session_state.cities.keys(), reverse=True))
city_data = st.session_state.cities[city_name]

all_centers = city_data["centers"]

raw_accidents = generate_random_accidents(bounds=city_data["bounds"], n=N_INCIDENTS, seed=42)
accidents = calculate_distances(all_centers, raw_accidents)
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
city_fleet.setdefault("vehicle_capacities", {})

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
    if selected["distances"]:
        service_label = SERVICE_CATEGORY_LABELS[selected["category"]]
        st.caption(f"Matching service: {service_label}")
        st.table([
            {
                "Service Site": d["name"],
                "Capacity": d["capacity"],
                "Distance (km)": d["distance_km"],
            }
            for d in selected["distances"]
        ])
    else:
        service_label = SERVICE_CATEGORY_LABELS[selected["category"]]
        st.warning(f"No {service_label.lower()} sites found for this city.")

st.sidebar.header("Map Layers")
visible_categories = {
    "hospital": st.sidebar.checkbox("Hospital", value=True),
    "fire": st.sidebar.checkbox("Fire", value=True),
    "police": st.sidebar.checkbox("Police", value=True),
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
tab_map, tab_fleet, tab_analytics, tab_benchmark = st.tabs(
    ["Map", "Fleet Assignment", "Analytics", "Optimiser vs Random"]
)

with tab_map:
    map_center = (city_data["center"]["lat"], city_data["center"]["lon"])
    city_map = build_dispatch_map(
        all_centers, accidents, selected_accident_id,
        visible_categories, center=map_center, assignments=city_fleet["assignments"],
    )
    folium_static(city_map, width=1200, height=700)

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
        "Set a Max Vehicles limit per site, and either edit Assigned manually "
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
                "Max Vehicles": city_fleet["vehicle_capacities"].get(c["name"], total),
                "Assigned": city_fleet["assignments"].get(c["name"], 0),
            }
            for c in matching_centers
        ]
        df = pd.DataFrame(table_rows)

        editor_key = f"editor_vehicles_{city_name}_{vehicle_type}_{st.session_state.fleet_version}"
        edited_df = st.data_editor(
            df,
            column_config={
                "Center": st.column_config.TextColumn(disabled=True),
                "Max Vehicles": st.column_config.NumberColumn(min_value=0, step=1),
                "Assigned": st.column_config.NumberColumn(min_value=0, step=1),
            },
            hide_index=True,
            key=editor_key,
        )

        for _, row in edited_df.iterrows():
            city_fleet["vehicle_capacities"][row["Center"]] = int(row["Max Vehicles"])
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
    assignment_method = st.radio(
        "Assignment method",
        ("Distance Optimizer", "Random"),
        horizontal=True,
        key=f"assignment_method_{city_name}",
    )
    st.caption(
        "The existing LP assigns incidents by minimum distance; fleet is then "
        "weighted by those incident counts and limited by each center's vehicle capacity."
        if assignment_method == "Distance Optimizer"
        else "Random allocation distributes vehicles while respecting each center's capacity."
    )

    if st.button(f"Run {assignment_method} Assignment"):
        proposed_assignments = {}
        errors = []
        capacity_warnings = []

        for vehicle_type, category in VEHICLE_TO_CATEGORY.items():
            matching_centers = [c for c in all_centers if c["category"] == category]
            total = city_fleet["totals"][vehicle_type]
            capacities = {
                c["name"]: city_fleet["vehicle_capacities"].get(c["name"], total)
                for c in matching_centers
            }

            if assignment_method == "Distance Optimizer":
                incident_counts = LP_Optimiser(
                    centers=matching_centers,
                    incidents=[
                        incident
                        for incident in accidents
                        if incident["category"] == category
                    ],
                    return_assignments=True,
                    verbose=False,
                )
                if incident_counts is None:
                    errors.append(
                        f"The distance optimizer could not assign {category} "
                        "incidents within the service-center capacities."
                    )
                    continue
                result = optimize_fleet_allocation(
                    centers=matching_centers,
                    total_vehicles=total,
                    capacities=capacities,
                    incidents=[],
                    incident_counts=incident_counts,
                )
            else:
                result = random_assignments(
                    centers=matching_centers,
                    total_vehicles=total,
                    capacities=capacities,
                )

            proposed_assignments.update(result)

            leftover = total - sum(result.values())
            if leftover > 0:
                capacity_warnings.append(
                    f"Could not place {leftover} {vehicle_type.lower()} — "
                    f"total capacity across all {category.lower()} is full."
                )

        if errors:
            st.session_state.fleet_assignment_feedback[city_name] = {
                "errors": errors,
                "warnings": [],
            }
        else:
            city_fleet["assignments"].update(proposed_assignments)
            st.session_state.fleet_assignment_feedback[city_name] = {
                "errors": [],
                "warnings": capacity_warnings,
            }
            st.session_state.fleet_version += 1
            st.rerun()

    feedback = st.session_state.fleet_assignment_feedback.get(city_name, {})
    for error in feedback.get("errors", []):
        st.error(error)
    for warning in feedback.get("warnings", []):
        st.warning(warning)

with tab_analytics:
    #st.subheader("Vehicle Distribution by Center")

    if city_fleet["assignments"]:
        fig = px.bar(
            x=list(city_fleet["assignments"].keys()),
            y=list(city_fleet["assignments"].values()),
            labels={"x": "Center", "y": "Vehicles Assigned"},
            title="Current Vehicle Allocation",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    #else:
       # st.info("Run the optimizer or manually assign vehicles to see this chart.")

    st.subheader("Incident Distances to Nearest Matching Service")
    if accidents:
        dist_df = pd.DataFrame([
            {
                "Incident": a["id"],
                "Incident Type": SERVICE_CATEGORY_LABELS[a["category"]],
                "Nearest Service (km)": a["distances"][0]["distance_km"],
            }
            for a in accidents
            if a["distances"]
        ])
        fig2 = px.bar(
            dist_df,
            x="Incident",
            y="Nearest Service (km)",
            color="Incident Type",
            title="Distance to Nearest Matching Service per Incident",
        )
        st.plotly_chart(fig2, use_container_width=True)

with tab_benchmark:
    st.subheader("Distance Optimiser vs Random Dispatch")
    st.caption(
        "Both methods assign the same incidents to matching service types and respect "
        "the same per-center incident capacities. The LP minimizes total distance."
    )
    trials = 1000
    seed = 42
    st.caption(f"Fixed benchmark: {trials:,} random trials (seed {seed}).")
    st.caption(
        "The nearest-center baseline assigns each incident to its closest matching "
        "center without enforcing capacity. The LP minimizes total distance while "
        "respecting center capacity."
    )

    if st.button("Run comparison", type="primary"):
        with st.spinner("Optimising and running random baselines..."):
            optimal = run_distance_optimiser(accidents, all_centers)
            if optimal is None:
                st.session_state["distance_benchmark"] = {
                    "city": city_name,
                    "error": "The incident assignment problem is infeasible under current capacities.",
                }
            else:
                baseline = compare_assignments(
                    accidents,
                    all_centers,
                    trials=int(trials),
                    seed=int(seed),
                )
                nearest = nearest_center_baseline(accidents, all_centers)
                st.session_state["distance_benchmark"] = {
                    "city": city_name,
                    "optimal": optimal,
                    "baseline": baseline,
                    "nearest": nearest,
                    "incident_count": len(accidents),
                    "trials": int(trials),
                }

    benchmark = st.session_state.get("distance_benchmark")
    if benchmark and benchmark["city"] == city_name:
        if "error" in benchmark:
            st.error(benchmark["error"])
        else:
            optimal = benchmark["optimal"]
            random_distances = benchmark["baseline"]["random"]
            greedy_distances = benchmark["baseline"]["greedy"]
            nearest = benchmark["nearest"]
            if not random_distances:
                st.warning("No random trials found a feasible assignment.")
            else:
                random_mean = sum(random_distances) / len(random_distances)
                improvement = 100 * (1 - optimal["total_km"] / random_mean)
                metric_columns = st.columns(4)
                metric_columns[0].metric(
                    "LP optimum",
                    f"{optimal['total_km']:.2f} km",
                )
                metric_columns[1].metric(
                    "Random mean",
                    f"{random_mean:.2f} km",
                    delta=f"{improvement:.1f}% shorter",
                    delta_color="normal",
                )
                metric_columns[2].metric(
                    "Best random",
                    f"{min(random_distances):.2f} km",
                )
                metric_columns[3].metric(
                    "Feasible random trials",
                    f"{len(random_distances)}/{benchmark['trials']}",
                )
                if nearest is not None:
                    st.metric(
                        "Nearest-center baseline",
                        f"{nearest['total_km']:.2f} km",
                    )
                    if nearest["over_capacity"]:
                        overloads = ", ".join(
                            f"{name}: +{count}"
                            for name, count in nearest["over_capacity"].items()
                        )
                        st.warning(
                            "The nearest-center baseline exceeds incident capacity "
                            f"at these centers: {overloads}."
                        )
                    else:
                        st.caption(
                            "The nearest-center baseline also fits within all "
                            "incident capacities."
                        )
                else:
                    st.warning(
                        "The nearest-center baseline could not assign every incident "
                        "because at least one incident has no matching center."
                    )

                if optimal["total_km"] <= min(random_distances) + 1e-6:
                    st.success(
                        f"The LP found an optimal assignment of {optimal['total_km']:.2f} km, "
                        f"beating or matching all {len(random_distances)} feasible random trials."
                    )
                else:
                    st.error(
                        "A random result was shorter than the LP result. Check the LP "
                        "inputs and constraints before presenting this comparison."
                    )

                chart_data = pd.DataFrame(
                    {"Random total distance (km)": random_distances}
                )
                figure = px.histogram(
                    chart_data,
                    x="Random total distance (km)",
                    nbins=40,
                    title="Capacity-respecting random assignment distances",
                )
                figure.add_vline(
                    x=optimal["total_km"],
                    line_color="green",
                    line_width=3,
                    annotation_text="LP optimum",
                )
                if nearest is not None:
                    figure.add_vline(
                        x=nearest["total_km"],
                        line_color="blue",
                        line_dash="dash",
                        annotation_text="Nearest center",
                    )
                st.plotly_chart(figure, use_container_width=True)

                if benchmark["baseline"]["random_infeasible"]:
                    st.caption(
                        f"{benchmark['baseline']['random_infeasible']} random trials "
                        "could not complete because an incident had no remaining-capacity site."
                    )
                if greedy_distances:
                    st.metric(
                        "Nearest-first greedy mean",
                        f"{sum(greedy_distances) / len(greedy_distances):.2f} km",
                    )

                st.subheader("LP assignment details")
                st.dataframe(
                    pd.DataFrame(optimal["rows"]),
                    hide_index=True,
                    use_container_width=True,
                )

    st.divider()
    st.subheader("Capacity stress test: LP vs nearest-first greedy")
    stress_trials = 50
    stress_incidents = 20
    stress_seed = 42
    capacity_override = st.slider(
        "Max incidents per center",
        min_value=1,
        max_value=5,
        value=2,
        key=f"stress_capacity_{city_name}",
    )
    stress_centers = [
        {**center, "capacity": min(int(center["capacity"]), capacity_override)}
        for center in all_centers
    ]
    feasible_incident_limit = sum(
        int(center["capacity"]) for center in stress_centers
    )
    actual_incident_count = min(stress_incidents, feasible_incident_limit)
    st.caption(
        f"Fixed stress test: {stress_trials} scenarios, up to {stress_incidents} "
        f"hotspot incidents per scenario, max {capacity_override} incidents per "
        f"center, seed {stress_seed}. Distances in this synthetic stress test are "
        "straight-line estimates; the regular benchmark above uses routed distances."
    )

    if st.button("Run capacity stress test"):
        with st.spinner(
            f"Running {stress_trials} capacity-constrained scenarios..."
        ):
            result = stress_test(
                centers=stress_centers,
                make_incidents=lambda scenario_seed: generate_hotspot_incidents(
                    stress_centers,
                    scenario_seed,
                    n_incidents=stress_incidents,
                ),
                run_optimum=run_distance_optimiser,
                trials=stress_trials,
                seed=stress_seed,
            )
            st.session_state["distance_stress_test"] = {
                "city": city_name,
                "capacity_override": capacity_override,
                "incident_count": actual_incident_count,
                "result": result,
            }

    stress_result = st.session_state.get("distance_stress_test")
    if (
        stress_result
        and stress_result["city"] == city_name
        and stress_result["capacity_override"] == capacity_override
    ):
        result = stress_result["result"]
        if result["lp_feasible"] == 0:
            st.error(
                "The LP could not find a feasible assignment in any stress scenario. "
                "Check the selected city's service-center capacities."
            )
        else:
            st.caption(
                f"Each scenario contained {stress_result['incident_count']} incidents."
            )
            stress_columns = st.columns(4)
            stress_columns[0].metric(
                "LP strictly shorter",
                f"{result['lp_strictly_better']}/{result['compared']}",
            )
            stress_columns[1].metric(
                "Mean greedy gap",
                f"{result['mean_gap_km']:.2f} km",
            )
            stress_columns[2].metric(
                "Worst greedy gap",
                f"{result['max_gap_km']:.2f} km",
            )
            stress_columns[3].metric(
                "Greedy dead-ends",
                f"{result['greedy_failures']}/{result['lp_feasible']}",
            )
            if result["greedy_failures"]:
                st.success(
                    f"Greedy could not complete {result['greedy_failures']} "
                    "scenarios that the LP solved."
                )
            if result["lp_strictly_better"]:
                st.success(
                    f"The LP found a shorter assignment in "
                    f"{result['lp_strictly_better']} of "
                    f"{result['compared']} scenarios where both methods completed."
                )
            elif not result["greedy_failures"]:
                st.info(
                    "The LP did not strictly improve on greedy in these scenarios. "
                    "Try a city with more concentrated service centers or tighter "
                    "capacity assumptions."
                )
            if result["lp_failures"]:
                st.warning(
                    f"The LP could not solve {result['lp_failures']} generated "
                    "scenarios; these are excluded from the comparison."
                )
    elif stress_result and stress_result["city"] == city_name:
        st.info("Run the stress test again to use the selected capacity limit.")
