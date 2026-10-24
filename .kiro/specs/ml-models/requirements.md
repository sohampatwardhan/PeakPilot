# ML models (SciPy and MATLAB) — Requirements

Issue: [#15](https://github.com/sohampatwardhan/PeakPilot/issues/15). Branch `feat/ml-models`, worktree `.worktrees/ml-models`.
Evidence: `studies/ml_studies.ipynb` at the repo root (executed, SIMULATED) and the scripts beside it. Numbers below are local
to this spec.

## Summary

Use machine learning where the studies show a measurable benefit and the steering allows it: as **analysis**
next to the deterministic scheduler, never as the scheduler. The studies found three such places:

1. **Reactive floor** (no ML). The "How close to optimal?" panel compares the LP bound with a run capped at the
   *chosen* limit, so Hot evening shows a 7.97 kW (57 %) gap. The lowest limit the reactive scheduler holds with
   all work done is 7.8 kW, only 1.77 kW above the 6.03 kW bound.
2. **Thermal calibration** (SciPy output-error fit). Recovers the room model to < 1 % from 4 h of thermostat-style
   data at 0.2 °C noise. A 30 %-wrong model moves the LP bound by −5 % to +16 %.
3. **Forecast sensitivity** (SciPy + existing LP). With good forecasts, planning could beat the reactive floor by
   1.0–1.7 kW. Timing and noise errors take most of that away, and a cool-biased outdoor forecast breaks comfort for
   462 min, so the panel shows what forecast error costs rather than claiming a saving.

MATLAB reproduces every fitted number to ~1e-8 and can call the engine through `pyenv`, but needs a licence. It
stays an optional cross-check off the judge's path.

## R1 — Reactive floor (`peakpilot/optimal.py`)

- R1.1 The system SHALL compute the reactive floor: the lowest power limit, on a 0.1 kW grid from 5.0 kW up to the
  uncoordinated peak rounded up (above which the limit never binds), at which the coordinated run has 0 minutes over the limit, every task met and 0 comfort-violation
  minutes. It SHALL call `engine.compare()` and SHALL NOT reimplement scheduling.
- R1.2 WHERE feasibility is not monotone in the limit (the EV-offline scenario is feasible only at 14.9–15.4 kW and
  at 19.0 kW and above), the system SHALL report the lowest feasible grid limit and SHALL state that higher limits are not all
  feasible.
- R1.3 IF no grid limit is feasible, THEN the panel SHALL say so and SHALL NOT show a floor number.
- R1.4 The "How close to optimal?" panel SHALL show the reactive floor beside the LP bound, with the headroom
  `floor − bound` in kW and %. This replaces the gap to the chosen limit as the headline number.
- R1.5 The search SHALL be cached on the scenario inputs and SHALL finish in under 1 s for every named scenario
  (measured without coverage tracing, which slows the engine about 3×).

## R2 — Thermal calibration (`peakpilot/learn.py`, new)

- R2.1 `learn.fit_thermal(room_c, outdoor_c, ac_kw)` SHALL fit `a = 1/(R·C)`, `b = eta/C` and the starting
  temperature by output-error nonlinear least squares (`scipy.optimize.least_squares`), seeded with an
  equation-error OLS estimate (`scipy.linalg.lstsq`).
- R2.2 It SHALL return the fitted `ThermalParams` (holding `C` fixed and mapping `a`, `b` to `R`, `eta`), the
  in-sample RMSE in °C, and the number of AC-on minutes used.
- R2.3 IF the series have unequal lengths, fewer than 60 points, or no AC-on minutes, THEN it SHALL raise
  `ValueError` with the reason.
- R2.4 Identical inputs SHALL give identical output. Any noise used for the demo SHALL be seeded.
- R2.5 The dashboard SHALL offer a "Calibrate the room model" expander that fits SIMULATED thermostat telemetry
  (the coordinated run plus seeded 0.2 °C noise), shows true vs fitted `R`, `eta` and the test RMSE, and states
  that a real building would supply measured telemetry.
- R2.6 Calibration SHALL NOT change the scenario the comparison runs on unless the user turns it on, and the
  panel SHALL say which room model is in use.

## R3 — Forecast sensitivity (`peakpilot/learn.py`)

- R3.1 `learn.forecast_cost(scenario, error)` SHALL build an LP plan on a perturbed base load / outdoor series and
  play it against the true series. It SHALL return planned peak, realized peak and comfort-violation minutes.
- R3.2 Supported errors SHALL be: base-load scale (0.8–1.2), timing shift (−60 to +60 min), seeded noise
  (0–0.5 kW) and outdoor bias (−3 to +3 °C).
- R3.3 The dashboard SHALL show a "What if the forecast is wrong?" control in the optimal panel, with realized peak
  against the reactive floor and the bound.
- R3.4 WHEN a plan breaks the comfort limit or does no better than the reactive floor, the panel SHALL say so.
- R3.5 The panel SHALL state that the plan is open-loop and that PeakPilot's control stays the reactive scheduler.

## R4 — Honesty and steering

- R4.1 Every value in R1–R3 SHALL carry the SIMULATED label. No cost or emissions claims.
- R4.2 No learned model SHALL make control decisions. `engine.py` SHALL stay stdlib-only and unchanged by this
  feature.
- R4.3 product.md SHALL list calibration and forecast sensitivity under In. "ML-based control" SHALL stay under Out.
- R4.4 tech.md and structure.md SHALL allow SciPy in `optimal.py` and `learn.py` only. CI's third-party guard on
  `engine.py` SHALL be unchanged.
- R4.5 This feature SHALL add nothing to the Raspberry Pi image (`rust/peakpilot-core`, built from that folder only).
  That image simulates what runs on the Pi. The studies, the notebook, `learn.py`, SciPy and MATLAB stay on the
  development machine and in the dashboard.

## R5 — MATLAB cross-check

- R5.1 `studies/s3_matlab_parity.m` SHALL stay runnable with base MATLAB + Optimization Toolbox and SHALL NOT be
  needed by the app, the tests or CI.
- R5.2 The README and `.kiro/KIRO_USAGE.md` SHALL describe MATLAB as an optional cross-check, with the measured
  agreement, and SHALL NOT imply that judges need MATLAB.

## R6 — Tests

- R6.1 `tests/test_learn.py` SHALL include property-based tests (Hypothesis): for any `a` in [0.02, 0.2] and `b` in
  [0.1, 1.0] and noise-free data with at least 30 AC-on minutes, `fit_thermal` recovers both within 1e-6 relative.
- R6.2 Tests SHALL check the R1.2 and R1.3 cases on the named scenarios: Hot evening floor 7.8 kW, EV offline
  non-monotone, plus a scenario with no feasible limit.
- R6.3 Tests SHALL check that `forecast_cost` with zero error returns the LP bound and 0 violation minutes.
- R6.4 `pytest -q --cov` SHALL stay green, with coverage of `peakpilot/` at or above 90 %.

## Acceptance criteria

1. Hot evening's panel shows reactive floor 7.8 kW, bound 6.03 kW, headroom 1.77 kW (≈ 23 %).
2. EV offline shows 14.9 kW with the "not all higher limits are feasible" note.
3. `fit_thermal` on the S1 telemetry (0.2 °C noise, 240 min) is within 1 % of the true `a` and `b`.
4. The forecast control reproduces the S2 Part A table to ±0.01 kW. The 0.5 kW noise row used the study's
   second noise draw, so `learn.forecast_cost` (one draw per seed) matches it in direction only.
5. `git diff main -- peakpilot/engine.py` is empty, and CI is green.

## Assumptions

- The thermal model has three numbers (`R`, `C`, `eta`) but only two combinations (`a`, `b`) are identifiable from
  temperature data. `C` is held at its default.
- Base-load forecasts in the dashboard are perturbations of the true series, not a trained forecaster. The studies
  show a trained one only on synthetic history, which the generator built the relationship into.

## Out of scope

Learned or forecast-driven control (MPC, RL), CSV upload of real telemetry (next step after this spec), MATLAB at
runtime, Compiler SDK packaging, neural networks, cost or carbon figures, and any change to the Raspberry Pi
image or the Rust engine.
