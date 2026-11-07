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
