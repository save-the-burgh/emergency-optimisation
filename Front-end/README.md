
# emergency-optimisation

Run via `python -m streamlit run dynamicapp.py`.

Install the pinned Python packages first with
`python -m pip install -r requirements.txt`. The requirements file was generated
from the active Python environment with `python -m pip freeze`.

For local Auth0 login, copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and replace the placeholder values with your Auth0
application credentials. Configure `http://localhost:8501` as an allowed
callback URL, logout URL, and web origin in Auth0. Keep `secrets.toml` private;
it is excluded from Git.

Each service site has a stable SHA-256 index derived from its category, name,
and coordinates. Capacities are deterministic simulation estimates in
concurrent incidents: hospitals are assigned 12–30, larger hospitals 30–60,
fire stations 2–4, and police stations 3–8. These are not verified
operational capacities.

The benchmark tab includes a fixed-capacity stress test comparing the LP with
randomized-order nearest-first greedy assignment across 50 reproducible hotspot
scenarios. It caps each site's incident capacity at two and uses up to 20
incidents per scenario (fewer where the city's combined capacity is lower).
These stress-test distances are straight-line estimates; the regular benchmark
uses routed distances. Treat the stress test as a controlled demonstration,
not as a forecast of real-world response performance.