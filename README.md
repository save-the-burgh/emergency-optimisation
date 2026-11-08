
# emergency-optimisation

Run via `python -m streamlit run dynamicapp.py`.

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

Each incident is routed only to service sites matching its type: hospital
incidents to hospitals, fire incidents to fire stations, and police incidents
to police stations. The saved distance list is sorted from nearest to farthest.