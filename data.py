import random
from geopy.distance import geodesic

def get_hospitals():
    
    return [
        {"name": "Royal Infirmary of Edinburgh", "lat": 55.9220, "lon": -3.1338},
        {"name": "Western General Hospital",     "lat": 55.9649, "lon": -3.2210},
        {"name": "Royal Edinburgh Hospital",     "lat": 55.9254, "lon": -3.2209},
        {"name": "Astley Ainslie Hospital",      "lat": 55.9316, "lon": -3.2075},
        {"name": "Liberton Hospital",            "lat": 55.9196, "lon": -3.1584},
    ]

EDINBURGH_BOUNDS = {
    "lat_min": 55.90, "lat_max": 55.97,
    "lon_min": -3.30, "lon_max": -3.10,
}

def generate_random_accidents(n=5, seed=None):
    
    if seed is not None:
        random.seed(seed)

    accidents = []
    for i in range(n):
        lat = random.uniform(EDINBURGH_BOUNDS["lat_min"], EDINBURGH_BOUNDS["lat_max"])
        lon = random.uniform(EDINBURGH_BOUNDS["lon_min"], EDINBURGH_BOUNDS["lon_max"])
        accidents.append({"id": f"A{i+1}", "lat": lat, "lon": lon})
    return accidents

def calculate_distances(hospitals, accidents):
    """
    copy pasted this - gives euclidian
    """
    enriched = []
    for a in accidents:
        distances = []
        for idx, h in enumerate(hospitals):
            km = geodesic((a["lat"], a["lon"]), (h["lat"], h["lon"])).km
            distances.append({
                "hospital_index": idx,
                "hospital": h["name"],
                "distance_km": round(km, 2),
            })
        distances.sort(key=lambda d: d["distance_km"])

        a_copy = dict(a)
        a_copy["distances"] = distances
        enriched.append(a_copy)

    return enriched
