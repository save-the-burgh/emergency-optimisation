import math
import random

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


def random_assignments(centers, total_vehicles, capacities, seed=None):
    """Randomly distribute vehicles without exceeding a center's capacity."""
    names = [center["name"] for center in centers]
    if not names:
        return {}
    if total_vehicles < 0:
        raise ValueError("total_vehicles cannot be negative")

    remaining_capacity = {
        name: max(0, int(capacities.get(name, total_vehicles))) for name in names
    }
    assignments = {name: 0 for name in names}
    pool = min(int(total_vehicles), sum(remaining_capacity.values()))
    rng = random.Random(seed)

    minimum_order = [name for name in names if remaining_capacity[name] > 0]
    rng.shuffle(minimum_order)
    for name in minimum_order:
        if pool == 0:
            break
        assignments[name] += 1
        remaining_capacity[name] -= 1
        pool -= 1

    available = [name for name in names if remaining_capacity[name] > 0]
    while pool and available:
        name = rng.choice(available)
        assignments[name] += 1
        remaining_capacity[name] -= 1
        pool -= 1
        if remaining_capacity[name] == 0:
            available.remove(name)

    return assignments


def optimize_assignments(centers, total_vehicles, capacities, historical_accidents=None):
    """Allocate vehicles to maximize diminishing returns from nearby incidents."""
    names = [center["name"] for center in centers]
    if not names:
        return {}
    if total_vehicles < 0:
        raise ValueError("total_vehicles cannot be negative")

    site_by_index = {center.get("index"): center["name"] for center in centers}
    capacity_by_name = {
        name: max(0, int(capacities.get(name, total_vehicles))) for name in names
    }
    assignments = {name: 0 for name in names}
    slots = []
    benefits = []
    demand = {name: 0.0 for name in names}

    for accident in historical_accidents or []:
        distances = accident.get("distances", [])
        weights = []
        for distance in distances:
            name = site_by_index.get(distance.get("index"), distance.get("name"))
            if name in demand:
                weights.append((name, 1.0 / (1.0 + float(distance["distance_km"]))))
        total_weight = sum(weight for _, weight in weights)
        if total_weight:
            for name, weight in weights:
                demand[name] += weight / total_weight

    if not any(demand.values()):
        demand = {name: 1.0 for name in names}
    else:
        baseline = max(demand.values()) * 1e-6
        demand = {name: score + baseline for name, score in demand.items()}

    for name in names:
        for unit in range(1, capacity_by_name[name] + 1):
            slots.append(name)
            benefits.append(demand[name] / math.sqrt(unit))

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
        raise RuntimeError(f"Vehicle allocation optimization failed: {result.message}")

    for index, name in enumerate(slots):
        if result.x[index] > 0.5:
            assignments[name] += 1
    return assignments
