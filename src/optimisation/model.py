from pulp import *
import json
import time 

start = time.time()

# Instantiate our problem class
model = LpProblem("Distance_minimisation_problem", LpMinimize)

# K — actual category names, not indices
K = ["hospital", "fire", "police"]

# Accident sites
# read from json file: accident_sites
accident_sites = json.load(open("data/raw/accident-sites.json"))

# # Accident sites id
# accident_sites_id = [site["id"] for site in accident_sites["incident_sites"]]

# Service sites
service_sites = json.load(open("data/raw/service-sites.json"))

# # service sites id
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
            print(f"Warning: service {service_id} not found in service_index_map")
            continue

        service_category = service_index_map[service_id]["category"]
        if service_category != k:
            continue  # skip if service site category does not match accident site category
        distance_matrix[acc_id][service_id] = float(service_site['distance_km'])

# print distance matrix
print(f"Distance matrix: {len(distance_matrix)} accident sites")
for acc_id, distances in distance_matrix.items():
    print(f"  Accident {acc_id} has {len(distances)} distances")
    for service_id, distance in distances.items():
        print(f"    Service {service_id}: {distance:.2f} km")


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
print(f"Accident sites by category: {A_k}")

# S_k — dict mapping each category to its service site indices
S_k = {k: [site["index"] for site in service_sites["centers"] if site["category"] == k] for k in K}
print(f"Service sites by category: {S_k}")

# Valid pairs - pairs where distance actually exists (i.e., where the service site is in the same category as the accident site)
valid_pairs = [
            (i, j) 
            for k in K 
            for i in A_k[k]
            for j in S_k[k]
            if j in distance_matrix[i]
]
print(f"Total valid pairs: {len(valid_pairs)}")
print(f"Sample valid pairs: {valid_pairs[:5]}")
print(f"Sample distances:")
for i, j in valid_pairs[:5]:
    print(f"  D[{i}][{j}] = {distance_matrix[i][j]:.2f} km")

# Decision variables

# 1. Binary variable x_ij: 1 if accident site i is assigned to service site j, 0 otherwise
X = LpVariable.dicts("X", valid_pairs, cat=LpBinary)


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
    model += lpSum([X[(i, j)] for j in valid_j]) == 1, f"Accident_{i}_assignment"

# 2. Each service site cannot exceed its maximum capacity
for k in K:
    for j in S_k[k]:
        valid_i = [i for i in A_k[k] if (i,j) in valid_pairs]
        model += lpSum([X[(i, j)] for i in valid_i]) <= capacity_matrix[j], f"Service_{j}_capacity"


# # 3. Binary constraint — only defined for matching category pairs:
# for k in K:
#     for i in A_k[k]:
#         for j in S_k[k]:
#             model += X[(i, j)] <= 1, f"Binary_constraint_{i}_{j}"

# 3. Sum of all assignments must equal the number of accidents

status = model.solve()
end = time.time()

print(f"Status:         {LpStatus[status]}")
print(f"Total Distance: {value(model.objective):.2f} km")
print(f"Solution time: {end - start:.2f} seconds")

for var in model.variables():
    print(var.name, "=", var.varValue)

print("variables: ", model.variables())

print("Min cost = ", value(model.objective))

print("Time elapsed: {}".format(end-start))

print("\nAssignments:")
for acc in accident_sites["incident_sites"]:
    i = acc["id"]
    k = acc["category"]
    for j in S_k[k]:
        if value(X[(i, j)]) == 1:
            # map service index to service name
            service_name = service_index_map[j]["name"]
            print(f"  [{k}] Accident {i} → Service {service_name} ({distance_matrix[i][j]:.2f} km)")
            # print(f"  [{k}] Accident {i} → Service {j} ({distance_matrix[i][j]:.2f} km)")


