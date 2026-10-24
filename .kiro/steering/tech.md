# PeakPilot — Tech Steering

## Stack

- **Language:** Python 3.11+ (developed on 3.15).
- **Simulation engine:** Python standard library only (`dataclasses`, `csv`, `json`, `enum`).
  Keeping the engine dependency-free makes it portable, fast to test, and trivial to import from
  any front end.
- **Dashboard:** Streamlit. Fastest route from a Python engine to an interactive, demo-ready UI.
- **Charts:** Plotly (via Streamlit) for the demand and temperature charts.
- **Data handling:** pandas for shaping MassGIS tables and simulation output for display.
- **Tests:** pytest for engine correctness (energy accounting, limits, deadlines, infeasibility,
  reproducibility).

All runtime dependencies are pinned in `requirements.txt`.

## Project layout

```
peakpilot/
  engine.py        # pure-stdlib simulation + scheduler (no UI imports)
  scenarios.py     # named, reproducible scenarios
  massgis.py       # loads bundled MassGIS CSVs, returns typed rows
app.py             # Streamlit dashboard (imports engine, never redefines control logic)
data/              # bundled MassGIS CSVs + a DATA.md provenance file
tests/             # pytest suite
```

## Engine conventions

- **Timestep:** 1 minute. Simulation window 16:00 → 08:00 (next day), 960 steps.
- **Units:** power in kW, energy in kWh, temperature in °C, time in minutes.
  `energy_kwh = power_kw * (minutes / 60)`.
- **Determinism:** no randomness in the control path. Same scenario → same result, every run.
  Any noise used for illustrative telemetry is seeded.
- **Separation:** `engine.py` imports no UI libraries. The dashboard calls `compare(scenario)`
  and renders the returned result; it must not reimplement scheduling.
- **Result shape:** the engine exposes a `to_json_dict()` so any front end (Streamlit now, a
  React app later) can consume the same output.

## Commands

- Setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run app: `streamlit run app.py`
- Tests: `pytest -q`

## IoT device interface

Every simulated device exposes `id`, `power_kw`, `online`, `last_update` (timestamp), and a set of
supported commands. A stale `last_update` flips the device to a visible OFFLINE/stale state. A real
sensor/controller could later implement the same interface without touching the scheduler.
