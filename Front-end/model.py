# from pulp import *
import math

import numpy as np
from pulp import (
    LpProblem,
    LpMinimize,
    LpVariable,
    LpBinary,
    LpSolveStatus,
    COIN_CMD,
    lpSum,
    value,
    LpInteger,
)
import json
import time 
from pathlib import Path
from scipy.optimize import Bounds, LinearConstraint, milp

def LP_Optimiser(
    city=None,
    *,
    centers=None,
    incidents=None,
    return_assignments=False,
    return_details=False,
    verbose=True,
):
    # Instantiate our problem class
    model = LpProblem("Distance_minimisation_problem", LpMinimize)
    def log(*args, **kwargs):
        if verbose:
            print(*args, **kwargs)

    # K — actual category names, not indices
    K = ["hospital", "fire", "police"]

    # Accident sites
    # read from json file: accident_sites
    import os.path

    if centers is None or incidents is None:
        if city is None:
            raise ValueError("Provide either city or both centers and incidents.")
        BASE_DIR = Path(__file__).resolve().parent
        incidence_path = BASE_DIR / "incidence_data" / f"{city}.json"
        city_path = BASE_DIR / "city_data" / f"{city}.json"

        with open(incidence_path, encoding="utf-8") as f:
            accident_sites = json.load(f)

        with open(city_path, encoding="utf-8") as f:
            service_sites = json.load(f)
    else:
        accident_sites = {"incident_sites": incidents}
        service_sites = {"centers": centers}
            # service_sites_id = [site["index"] for site in service_sites["centers"]]
    # Distance matrix
    # distance matrix would have three levels: accident id, category, service id

    # map of service index to service
    service_index_map = {site["index"]: site for site in service_sites["centers"]}
    distance_matrix = {}
    for acc in accident_sites["incident_sites"]:
        acc_id = acc["id"]
        k = acc["category"]

        distance_matrix[acc_id] = {}

        for service_site in acc['distances']:
            service_id = service_site['index']
            service_name = service_site['name']
            if service_id not in service_index_map:   #guard against missing IDs
                log(f"Warning: service {service_id} not found in service_index_map")
                continue

            service_category = service_index_map[service_id]["category"]
            if service_category != k:
                continue  # skip if service site category does not match accident site category
            distance_matrix[acc_id][service_id] = float(service_site['distance_km'])

    # print distance matrix
    log(f"Distance matrix: {len(distance_matrix)} accident sites")
    for acc_id, distances in distance_matrix.items():
        log(f"  Accident {acc_id} has {len(distances)} distances")
        for service_id, distance in distances.items():
            log(f"    Service {service_id}: {distance:.2f} km")


    # print(f"Accidents in distance_matrix: {len(distance_matrix)}")
    # print(f"Sample entry: {list(distance_matrix.items())[0]}")
    # for acc in accident_sites["incident_sites"]:
    #     i = acc["id"]
    #     print(f"Accident {i} has {len(distance_matrix[i])} distances")


    # Capacity matrix
    capacity_matrix = {}
    for site in service_sites["centers"]:
        site_id = site["index"]
        capacity_matrix[site_id] = site["capacity"]


    # Sets =========================

    # A — flat list of accident site indices
    A = [acc["id"] for acc in accident_sites["incident_sites"]]

    # S — flat list of service site indices
    S = [site["index"] for site in service_sites["centers"]]


    # A_k — dict mapping each category to its accident site indices
    A_k = {k: [acc["id"] for acc in accident_sites["incident_sites"] if acc["category"] == k] for k in K}
    log(f"Accident sites by category: {A_k}")

    # S_k — dict mapping each category to its service site indices
    S_k = {k: [site["index"] for site in service_sites["centers"] if site["category"] == k] for k in K}
    log(f"Service sites by category: {S_k}")

    # Valid pairs - pairs where distance actually exists (i.e., where the service site is in the same category as the accident site)
    valid_pairs = [
                (i, j) 
                for k in K 
                for i in A_k[k]
                for j in S_k[k]
                if j in distance_matrix[i]
    ]
    log(f"Total valid pairs: {len(valid_pairs)}")
    log(f"Sample valid pairs: {valid_pairs[:5]}")
    log("Sample distances:")
    for i, j in valid_pairs[:5]:
        log(f"  D[{i}][{j}] = {distance_matrix[i][j]:.2f} km")

    # Decision variables
    # 1. Binary variable x_ij: 1 if accident site i is assigned to service site j, 0 otherwise
    #X = LpVariable.add_variable_dicts("X", valid_pairs, cat=LpBinary)
    ## equivalent to 4 version? 
    # prob = LpProblem("Distance_minimisation_problem", LpMinimize)
    # X = prob.add_variable_dicts("X", valid_pairs, cat=LpInteger)

    X = {
        (i, j): model.add_variable(f"X_{i}_{j}", cat=LpBinary)
        for (i, j) in valid_pairs
    }
    # OBJECTIVE FUNCTION =========================
    # minimise the distance between accident sites and service sites
    # X_ij * distance_ij where distance_ij is the distance between accident site i and service site j
    model += lpSum([X[(i, j)] * distance_matrix[i][j] for (i, j) in valid_pairs]), "Total_Distance"

    # CONSTRAINTS =========================
    # 1. Each accident is assigned to exactly one service site OF ITS category
    for acc in accident_sites["incident_sites"]:
        i = acc["id"]
        k = acc["category"]
        valid_j = [j for j in S_k[k] if j in distance_matrix[i]]
        model += lpSum([X[(i, j)] for j in valid_j if (i, j) in X]) == 1, f"Accident_{i}_assignment"

    # 2. Each service site cannot exceed its maximum capacity
    for k in K:
        for j in S_k[k]:
            valid_i = [i for i in A_k[k] if (i, j) in valid_pairs]
            model += lpSum([X[(i, j)] for i in valid_i]) <= capacity_matrix[j], f"Service_{j}_capacity"


    # # 3. Binary constraint — only defined for matching category pairs:
    # for k in K:
    #     for i in A_k[k]:
    #         for j in S_k[k]:
    #             model += X[(i, j)] <= 1, f"Binary_constraint_{i}_{j}"

    # 3. Sum of all assignments must equal the number of accidents

    solve_start = time.time()
    status = model.solve(COIN_CMD(msg=verbose))
    end = time.time()

    log("Status:", status.status_str)
    if not status.has_solution or status.status not in {
        LpSolveStatus.Optimal,
        LpSolveStatus.GapLimit,
    }:
        return None
    if status.status == LpSolveStatus.GapLimit and (
        status.gap_abs is None
        or status.objective is None
        or status.gap_abs > 1e-8 * max(1.0, abs(status.objective))
    ):
        return None
    log(f"Total Distance: {value(model.objective):.2f} km")
    log(f"Solution time: {end - solve_start:.2f} seconds")

    for var in model.variables():
        log(var.name, "=", var.varValue)

    log("variables: ", model.variables())

    log("Min cost = ", value(model.objective))

    log("Time elapsed: {}".format(end-solve_start))

    log("\nAssignments:")
    assignment_counts = {site["name"]: 0 for site in service_sites["centers"]}
    for acc in accident_sites["incident_sites"]:
        i = acc["id"]
        k = acc["category"]
        for j in S_k[k]:
            if (i, j) in X and value(X[(i, j)]) == 1:
                # map service index to service name
                service_name = service_index_map[j]["name"]
                assignment_counts[service_name] += 1
                log(f"  [{k}] Accident {i} -> Service {service_name} ({distance_matrix[i][j]:.2f} km)")
                # print(f"  [{k}] Accident {i} → Service {j} ({distance_matrix[i][j]:.2f} km)")

    if return_details:
        rows = []
        for (i, j) in valid_pairs:
            if value(X[(i, j)]) > 0.5:
                service = service_index_map[j]
                rows.append({
                    "Incident": i,
                    "Type": service["category"],
                    "Assigned station": service["name"],
                    "Distance (km)": distance_matrix[i][j],
                })
        return {"total_km": value(model.objective), "rows": rows}

    return assignment_counts if return_assignments else distance_matrix


def optimize_fleet_allocation(
    centers, total_vehicles, capacities, incidents, incident_counts=None
):
    """Allocate fleet to centers based on incident proximity and center capacity."""
    names = [center["name"] for center in centers]
    assignments = {name: 0 for name in names}
    if not names or total_vehicles <= 0:
        return assignments

    center_by_index = {center.get("index"): center["name"] for center in centers}
    demand = {name: 0.0 for name in names}
    if incident_counts is not None:
        demand = {
            name: float(incident_counts.get(name, 0))
            for name in names
        }
    else:
        for incident in incidents:
            weights = []
            for distance in incident.get("distances", []):
                name = center_by_index.get(distance.get("index"), distance.get("name"))
                if name in demand:
                    weights.append((name, 1 / (1 + float(distance["distance_km"]))))
            total_weight = sum(weight for _, weight in weights)
            if total_weight:
                for name, weight in weights:
                    demand[name] += weight / total_weight

    if not any(demand.values()):
        demand = {name: 1.0 for name in names}
    else:
        baseline = max(demand.values()) * 1e-6
        demand = {name: score + baseline for name, score in demand.items()}

    slots = []
    benefits = []
    for name in names:
        capacity = max(0, int(capacities.get(name, 0)))
        for vehicle_number in range(1, capacity + 1):
            slots.append(name)
            benefits.append(demand[name] / math.sqrt(vehicle_number))

    vehicle_count = min(int(total_vehicles), len(slots))
    if vehicle_count == 0:
        return assignments

    result = milp(
        c=-np.asarray(benefits),
        integrality=np.ones(len(slots), dtype=int),
        bounds=Bounds(np.zeros(len(slots)), np.ones(len(slots))),
        constraints=LinearConstraint(
            np.ones((1, len(slots))),
            np.array([vehicle_count]),
            np.array([vehicle_count]),
        ),
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"Fleet allocation optimization failed: {result.message}")

    for index, name in enumerate(slots):
        if result.x[index] > 0.5:
            assignments[name] += 1
    return assignments
if __name__ == "__main__":
    LP_Optimiser("edinburgh")