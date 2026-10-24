# PeakPilot — Requirements

Concise requirements for a 6–7 hour hackathon build. EARS-style acceptance criteria, numbered for
traceability. Track: Energy & climate tech (C3 — clean power at the peak).

## R1 — Simulation engine (deterministic core)

**Story:** As a facilities manager, I want the same evening simulated with and without
coordination so I can see what coordination changes.

- R1.1 The engine SHALL simulate a 16:00→08:00 window in 1-minute steps (960 steps).
- R1.2 The engine SHALL model three devices: EV charger (throttleable), water heater (on/off with
  minimum run), air conditioner (on/off with minimum run, driven by a room thermal model).
- R1.3 The engine SHALL compute energy as `power_kw * minutes/60` and track delivered kWh per device.
- R1.4 For a given scenario the baseline and coordinated runs SHALL use identical workloads,
  initial conditions, and environmental inputs.
- R1.5 The engine SHALL be deterministic: identical scenario inputs produce identical outputs.
- R1.6 The engine SHALL import only the Python standard library.

## R2 — Coordinated control (least-slack-first, explainable)

**Story:** As a facilities manager, I want a controller that keeps the building under a power limit
while meeting device needs, and tells me why it acted.

- R2.1 The controller SHALL hold total demand at or below the configured power limit whenever
  feasible.
- R2.2 The controller SHALL allocate power least-slack-first (slack = time to deadline − time
  needed at full power).
- R2.3 WHEN a task's slack reaches zero, the controller SHALL run it at full power even if that
  exceeds the limit, and SHALL record the breach.
- R2.4 The controller SHALL respect device minimum run times (no sub-minimum cycling).
- R2.5 The controller SHALL keep the simulated room at or below the comfort limit whenever feasible,
  prioritizing the AC when the room approaches the limit.
- R2.6 The controller SHALL emit a plain-language decision-log entry on each state change only.

## R3 — Honest metrics and infeasibility

**Story:** As a reviewer, I want honest results, including failures.

- R3.1 The engine SHALL report per run: peak kW, total kWh, per-device delivered kWh, tasks met,
  minutes over limit, and temperature-violation minutes.
- R3.2 WHEN a scenario is infeasible, the engine SHALL report unmet energy, missed deadlines, and
  minutes over limit rather than hiding them.
- R3.3 The comparison SHALL include the recovery period (deferred load remains visible in the window).
- R3.4 The engine SHALL NOT reduce peak by leaving required work unfinished and calling it success.

## R4 — Offline / stale IoT behavior

**Story:** As a facilities manager, I want the system to behave sensibly when a device drops offline.

- R4.1 Each device SHALL expose id, power_kw, online flag, last_update timestamp, and supported commands.
- R4.2 WHEN a device is offline, the controller SHALL assume it holds its last commanded power,
  reserve that headroom, and disclose the assumption in the log.
- R4.3 WHEN a reading is stale, the dashboard SHALL mark the device OFFLINE/stale visibly.

## R5 — Dashboard (reviewer can use it without reading code)

**Story:** As a reviewer, I want to select inputs, run, and read results.

- R5.1 The dashboard SHALL let the user pick a scenario, set the power limit, and set EV/water-heater
  energy and deadlines.
- R5.2 The dashboard SHALL show a before/after demand chart with the limit line, and a room-temperature chart.
- R5.3 The dashboard SHALL show metric cards: peak kW, peak reduction %, total kWh, minutes over limit, tasks met.
- R5.4 The dashboard SHALL show the decision log and a per-device status panel (id, kW, online/OFFLINE, last update).
- R5.5 The dashboard SHALL provide reproducible scenario buttons and a reset control.
- R5.6 All simulated telemetry SHALL be labeled SIMULATED in the UI.

## R6 — MassGIS context (honest, bundled)

**Story:** As a facilities manager, I want local Massachusetts context for the selected town.

- R6.1 The dashboard SHALL let the user select a Massachusetts town and show its listed electric utility.
- R6.2 The dashboard SHALL show listed landfill renewable projects for that town (status, reported MW).
- R6.3 MassGIS data SHALL be bundled (no runtime network calls) with documented source URLs,
  retrieval date, units, missing-value handling, and usage terms.
- R6.4 The UI SHALL distinguish MassGIS facts from simulation outputs, and SHALL NOT infer generation
  from installed capacity, nor claim price/carbon/supply relationships.

## R7 — Submission artifacts

- R7.1 The repo SHALL include runnable source, pinned dependencies, and setup instructions.
- R7.2 The repo SHALL commit `.kiro/` (steering + Kiro usage write-up) and `.specs/`.
- R7.3 The README SHALL cover setup, demo steps, assumptions, limitations, and dataset attribution.
- R7.4 The repo SHALL include a ≤2:30 demo script and a submission checklist. Publishing/submitting
  is a manual step, not automated.
