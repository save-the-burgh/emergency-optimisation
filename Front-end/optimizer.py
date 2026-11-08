import random


def optimize_assignments(centers, total_vehicles, capacities, historical_accidents=None):
    """
    PLACEHOLDER optimizer.

    Currently: guarantees at least 1 vehicle per center (capacity/pool
    permitting), then randomly distributes any remaining vehicles,
    never exceeding each center's capacity.

    `historical_accidents` is accepted but unused for now — the real
    optimizer will use it to weight assignments toward high-demand
    centers instead of choosing randomly. Keep this parameter when you
    swap in the real logic, so app.py doesn't need to change.

    Args:
        centers: list of dicts with 'name' — ONE category only
        total_vehicles: int, number of vehicles available to distribute
        capacities: dict mapping center name -> max vehicles allowed there
        historical_accidents: unused placeholder for the real optimizer

    Returns:
        dict mapping center name -> assigned vehicle count.
        Sum of values may be LESS than total_vehicles if total capacity
        is smaller than total_vehicles. Some centers may get 0 if
        total_vehicles is smaller than the number of centers.
    """
    names = [c["name"] for c in centers]
    if not names:
        return {}

    remaining_capacity = {name: capacities.get(name, total_vehicles) for name in names}
    assignment = {name: 0 for name in names}
    pool = total_vehicles

    # --- Step 1: guarantee at least 1 vehicle per center, where possible ---
    # Shuffle order so the same centers aren't always favored when the
    # pool runs out before every center gets its minimum.
    minimum_order = [name for name in names if remaining_capacity[name] > 0]
    random.shuffle(minimum_order)

    for name in minimum_order:
        if pool <= 0:
            break
        assignment[name] += 1
        remaining_capacity[name] -= 1
        pool -= 1

    # --- Step 2: randomly distribute any leftover vehicles ---
    available = [name for name in names if remaining_capacity[name] > 0]
    while pool > 0 and available:
        choice = random.choice(available)
        assignment[choice] += 1
        remaining_capacity[choice] -= 1
        pool -= 1
        if remaining_capacity[choice] <= 0:
            available.remove(choice)

    return assignment
