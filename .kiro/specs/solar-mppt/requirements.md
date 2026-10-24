# On-site solar with MPPT — Requirements

Issue: [#33](https://github.com/sohampatwardhan/PeakPilot/issues/33). Branch `feat/solar-mppt`.
Sized for a ~1 hour slot. Numbers below are local to this spec.

## Summary

Add an optional SIMULATED rooftop PV array whose inverter tracks the array's maximum power point
(MPPT) with a perturb-and-observe controller. PV output offsets building demand, so the scheduler
holds **net grid import** (base load + devices − PV) under the power limit. Scenarios without solar
behave exactly as before.

## R1 — PV array and MPPT (`peakpilot/engine.py`, stdlib only)

- R1.1 The array SHALL be modeled by an ideal single-diode I-V curve whose short-circuit current scales
  with irradiance and whose currents and voltages shift with cell temperature.
- R1.2 Cell temperature SHALL follow the NOCT approximation from the scenario's outdoor temperature
  and irradiance.
- R1.3 The inverter SHALL run a perturb-and-observe MPPT loop each minute, starting from the operating
  voltage it held the minute before.
- R1.4 The reported PV power SHALL NOT exceed the array's true maximum power point (found
  independently) after inverter efficiency, nor the inverter's AC rating.
- R1.5 WHEN irradiance is zero, PV output SHALL be zero.
- R1.6 The engine SHALL report PV energy (kWh) and MPPT tracking efficiency (tracked ÷ true MPP DC
  energy over sunlit minutes).
- R1.7 Identical scenarios SHALL produce identical PV output (no randomness).

## R2 — Scheduling against net load

- R2.1 WHEN a scenario has solar, both runs SHALL subtract the same PV series from building demand,
  and `total_kw`, `peak_kw`, `total_kwh` and minutes over limit SHALL describe net grid import.
- R2.2 The coordinated scheduler SHALL use net base load (base − PV) for headroom and for the water
  heater's minimum-run forecast.
- R2.3 WHEN a scenario has no solar, every result and the JSON output SHALL be unchanged (Rust parity
  holds without Rust changes).
- R2.4 The LP benchmark (`optimal.py`) SHALL use the same net base load when solar is present.

## R3 — Scenario, dashboard and honesty

- R3.1 A named scenario "Sunny evening + rooftop PV" SHALL add solar to the tight 11 kW case.
- R3.2 The irradiance profile SHALL be an illustrative clear-sky curve, labeled SIMULATED, and SHALL
  NOT be derived from MassGIS installed capacity.
- R3.3 The dashboard SHALL plot PV output and show PV energy and MPPT tracking efficiency, labeled
  SIMULATED, with no cost or emissions claims.
- R3.4 The Rust engine port of PV is out of scope; the spec and README SHALL say so.
