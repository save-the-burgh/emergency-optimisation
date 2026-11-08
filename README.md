# emergency-optimisation

## Computing the nearest service routes

Run the staged route generator from the repository root:

```bash
PYTHONPATH=. .venv/bin/python src/optimisation/compute_nearest_routes.py
```

The script:

1. Loads and validates the accident and service site JSON files.
2. Geocodes each site with Nominatim.
3. Requests full driving routes from OSRM for each accident and its required
   service categories.
4. Sorts routes by driving distance and keeps the two shortest routes.
5. Writes `src/optimisation/nearest_routes.json`.

The output is keyed by accident site ID. Each value is a list of up to two
routes containing `service_site_id`, `distance_m`, `duration_s`, and a GeoJSON
`geometry` object with the route coordinates. Use `--top N` to change the
number of routes or `--output PATH` to choose another output file.


# 🚨 Edinburgh Emergency Resource Optimisation

A prototype tool for visualising and optimising the allocation of emergency
service resources (hospitals, fire stations, police stations) to accident
sites across Edinburgh.

---

## 📋 Table of Contents
- [Overview](#overview)
- [Data Sources](#data-sources)
- [Mathematical Formulation](#mathematical-formulation)
  - [Sets](#sets)
  - [Parameters](#parameters)
  - [Decision Variables](#decision-variables)
  - [Objective Function](#objective-function)
  - [Constraints](#constraints)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)

---

## 🔍 Overview

This tool takes **accident site addresses as input**, geocodes them into
coordinates, and solves an assignment problem that minimises the total
distance between accident sites and emergency service sites.

A **crime heatmap** by Edinburgh ward is also displayed for situational
awareness, and will be incorporated into the optimisation in future iterations.

---

## 📂 Data Sources

| Data | Format | Source |
|------|--------|--------|
| Service sites (hospitals, fire, police) | `service_sites.json` | Manually verified |
| Accident site addresses | User input / CSV | Geocoded via GeoPy |
| Crime by ward (2020–2025) | `crime_by_ward.html` | City of Edinburgh Council |
| Ward boundaries | `edinburgh_wards.geojson` | spatialdata.gov.scot |

---

## 📐 Mathematical Formulation

### Sets

| Notation | Description |
|----------|-------------|
| $A$ | Set of accident sites, each defined by a geocoded coordinate |
| $S$ | Set of all service sites |
| $S_k \subseteq S$ | Subset of service sites of category $k$ |
| $K$ | Set of service categories: {hospital, fire_service, police_service} |

---

### Parameters

| Notation | Description | Source |
|----------|-------------|--------|
| $(\phi_i^A, \lambda_i^A)$ | Latitude & longitude of accident site $i$ | Geocoded from input address |
| $(\phi_j^S, \lambda_j^S)$ | Latitude & longitude of service site $j$ | `service_sites.json` |
| $d_{ij}$ | Haversine distance between accident $i$ and service site $j$ | Computed |

Distance $d_{ij}$ is computed using the Haversine formula:

$$d_{ij} = 2R \\arcsin\\left(\\sqrt{\\sin^2\\left(\\frac{\\phi_j^S - \\phi_i^A}{2}\\right) + \\cos(\\phi_i^A)\\cos(\\phi_j^S)\\sin^2\\left(\\frac{\\lambda_j^S - \\lambda_i^A}{2}\\right)}\\right)$$

Where $R = 6{,}371$ km is the Earth's radius.

---

### Decision Variables

$$x_{ij} = \begin{cases} 1 & \text{if accident site } i \text{ is assigned to service site } j \\ 0 & \text{otherwise} \end{cases}$$

---

### Objective Function

Minimise the total distance between all accident sites and their
assigned service sites across all categories:

$$\min \sum_{i \in A} \sum_{j \in S} d_{ij} \cdot x_{ij}$$

---

### Constraints

**1. Each accident must be assigned to exactly one service site per category:**

$$\sum_{j \in S_k} x_{ij} = 1 \qquad \forall i \in A,\ \forall k \in K$$

**2. Binary constraint on decision variables:**

$$x_{ij} \in \{0, 1\} \qquad \forall i \in A,\ \forall j \in S$$

---

## 🗂️ Project Structure
