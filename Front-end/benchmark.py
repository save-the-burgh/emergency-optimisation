import random
import math


def _run_assignment(incidents, centers, rng, choose):
    remaining_capacity = {
        center["index"]: int(center["capacity"]) for center in centers
    }
    total_distance = 0.0

    for incident in rng.sample(incidents, len(incidents)):
        options = [
            distance
            for distance in incident["distances"]
            if distance["category"] == incident["category"]
            and remaining_capacity.get(distance["index"], 0) > 0
        ]
        if not options:
            return None

        chosen = choose(options, rng)
        remaining_capacity[chosen["index"]] -= 1
        total_distance += float(chosen["distance_km"])

    return total_distance


def random_assignment_distance(incidents, centers, rng):
    """Return a capacity-respecting random assignment distance, or None."""
    return _run_assignment(
        incidents, centers, rng, lambda options, randomizer: randomizer.choice(options)
    )


def greedy_assignment_distance(incidents, centers, rng):
    """Return a randomized-order nearest-first distance, or None if infeasible."""
    return _run_assignment(
        incidents,
        centers,
        rng,
        lambda options, randomizer: min(options, key=lambda option: option["distance_km"]),
    )


def nearest_center_baseline(incidents, centers):
    """Assign each incident to its nearest matching center without capacity limits."""
    centers_by_index = {center["index"]: center for center in centers}
    assignments = {center["name"]: 0 for center in centers}
    rows = []
    total_distance = 0.0

    for incident in incidents:
        options = [
            distance
            for distance in incident["distances"]
            if distance["category"] == incident["category"]
            and distance["index"] in centers_by_index
        ]
        if not options:
            return None

        chosen = min(options, key=lambda option: option["distance_km"])
        center = centers_by_index[chosen["index"]]
        assignments[center["name"]] += 1
        total_distance += float(chosen["distance_km"])
        rows.append({
            "Incident": incident["id"],
            "Assigned station": center["name"],
            "Distance (km)": float(chosen["distance_km"]),
        })

    over_capacity = {
        center["name"]: max(
            0, assignments[center["name"]] - int(center["capacity"])
        )
        for center in centers
        if assignments[center["name"]] > int(center["capacity"])
    }
    return {
        "total_km": total_distance,
        "rows": rows,
        "assignments": assignments,
        "over_capacity": over_capacity,
    }


def generate_hotspot_incidents(centers, seed, n_incidents=20):
    """Build a reproducible synthetic hotspot using straight-line distances."""
    rng = random.Random(seed)
    centers_by_category = {}
    for center in centers:
        centers_by_category.setdefault(center["category"], []).append(center)
    available_categories = sorted(
        category
        for category, category_centers in centers_by_category.items()
        if category_centers
    )
    if not available_categories:
        return []

    quotas = {category: 0 for category in available_categories}
    for _ in range(n_incidents):
        eligible = [
            category
            for category in available_categories
            if quotas[category]
            < sum(
                max(0, int(center["capacity"]))
                for center in centers_by_category[category]
            )
        ]
        if not eligible:
            break
        category = min(
            eligible,
            key=lambda item: (
                quotas[item]
                / sum(
                    max(0, int(center["capacity"]))
                    for center in centers_by_category[item]
                ),
                item,
            ),
        )
        quotas[category] += 1

    incidents = []
    for category in available_categories:
        category_centers = centers_by_category[category]
        if not quotas[category]:
            continue
        hotspot = max(
            category_centers,
            key=lambda candidate: sum(
                _distance_km(candidate["lat"], candidate["lon"], other["lat"], other["lon"])
                <= 5
                for other in category_centers
            ),
        )
        for _ in range(quotas[category]):
            lat = hotspot["lat"] + rng.gauss(0, 0.008)
            lon = hotspot["lon"] + rng.gauss(
                0, 0.008 / max(math.cos(math.radians(hotspot["lat"])), 0.1)
            )
            distances = [
                {
                    "index": center["index"],
                    "name": center["name"],
                    "category": category,
                    "capacity": center["capacity"],
                    "distance_km": _distance_km(
                        lat, lon, center["lat"], center["lon"]
                    ),
                }
                for center in category_centers
            ]
            distances.sort(key=lambda distance: distance["distance_km"])
            incidents.append({
                "id": f"{category}-{seed}-{len(incidents) + 1}",
                "category": category,
                "lat": lat,
                "lon": lon,
                "distances": distances,
            })
    return incidents


def _distance_km(lat1, lon1, lat2, lon2):
    earth_radius_km = 6371.0
    latitude_delta = math.radians(lat2 - lat1)
    longitude_delta = math.radians(lon2 - lon1)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(haversine))


def stress_test(centers, make_incidents, run_optimum, trials=50, seed=42):
    """Compare the LP with randomized-order nearest-first greedy scenarios."""
    if trials < 1:
        raise ValueError("trials must be at least 1")

    lp_feasible = 0
    greedy_failures = 0
    lp_failures = 0
    strictly_better = 0
    gaps = []
    for scenario_seed in range(seed, seed + trials):
        incidents = make_incidents(scenario_seed)
        result = run_optimum(incidents, centers)
        if result is None:
            lp_failures += 1
            continue
        lp_feasible += 1
        lp_distance = (
            float(result["total_km"])
            if isinstance(result, dict)
            else float(result)
        )
        greedy_distance = greedy_assignment_distance(
            incidents, centers, random.Random(scenario_seed)
        )
        if greedy_distance is None:
            greedy_failures += 1
            continue
        gap = greedy_distance - lp_distance
        gaps.append(gap)
        if gap > 1e-6:
            strictly_better += 1

    return {
        "trials": trials,
        "lp_feasible": lp_feasible,
        "lp_failures": lp_failures,
        "greedy_failures": greedy_failures,
        "lp_strictly_better": strictly_better,
        "compared": len(gaps),
        "mean_gap_km": sum(gaps) / len(gaps) if gaps else 0.0,
        "max_gap_km": max(gaps) if gaps else 0.0,
    }


def compare_assignments(incidents, centers, trials=1000, seed=0):
    """Compare random and greedy baselines under the same center capacities."""
    if trials < 1:
        raise ValueError("trials must be at least 1")

    rng = random.Random(seed)
    random_distances = []
    greedy_distances = []
    for _ in range(trials):
        random_distance = random_assignment_distance(incidents, centers, rng)
        if random_distance is not None:
            random_distances.append(random_distance)
        greedy_distance = greedy_assignment_distance(incidents, centers, rng)
        if greedy_distance is not None:
            greedy_distances.append(greedy_distance)
    return {
        "random": random_distances,
        "greedy": greedy_distances,
        "random_infeasible": trials - len(random_distances),
        "greedy_infeasible": trials - len(greedy_distances),
    }
