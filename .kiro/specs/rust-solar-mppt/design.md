# Rust solar port + solar study — Design

Issue: [#35](https://github.com/sohampatwardhan/PeakPilot/issues/35).

## Rust

- New `src/solar.rs` (std only): `PVArray` (`Default` = Python defaults), `Solar`,
  `SolarResult`, `pv_curve`, `pv_power_w`, `true_mpp_w`, `simulate_solar`, `pv_kw_series`.
  Python `min`/`max` semantics are written out explicitly (`py_min`, `py_max`), and `pv_kwh`
  uses `py_sum` (CPython's compensated `sum()`).
- `Scenario.solar: Option<Solar>`; `CompareResult.solar: Option<SolarResult>`.
- `engine.rs`: `total = py_sum(devices) + base[m] − pv[m]`; `committed = base[m] − pv[m]`;
  water-heater forecast takes the max of `base[t] − pv[t]` (first maximum, as Python's `max`).
- `scenarios.rs`: `ScenarioParams.solar: bool`, `clear_sky_irradiance()` (same expression and
  `round4`), `sunny_evening_params()`; `all()` grows to five entries.
- `json.rs`: `#[serde(skip_serializing_if = "Option::is_none")] solar`.
- Python side: `custom_scenario(..., solar=False)` so the parity table can rebuild
  `sunny_evening()`; `sunny_evening()` uses it (same scenario as before).

## Study S4

- Part A: tracking efficiency on the sunny scenario for step ∈ {0.5, 1, 2, 5, 10} V and
  iterations ∈ {1, 5, 20}, plus a minute-by-minute trace near sunset.
- Part B: tight 11 kW workload with and without PV: uncoordinated peak, reactive floor (lowest
  limit held with all deadlines met, 0 min over, 0 min above comfort; 0.1 kW sweep), LP bound.
- Results JSON pinned by `tests/test_solar.py` (study reproduction test).
