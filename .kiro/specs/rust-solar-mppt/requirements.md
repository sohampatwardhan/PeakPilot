# Rust solar port + solar study — Requirements

Issue: [#35](https://github.com/sohampatwardhan/PeakPilot/issues/35). Branch `feat/rust-solar-mppt`.
Follows [#33](https://github.com/sohampatwardhan/PeakPilot/issues/33) (`.kiro/specs/solar-mppt/`).
Numbers below are local to this spec.

## R1 — Rust engine parity for solar (`rust/peakpilot-core`)

- R1.1 The Rust core SHALL model `PVArray`, `Solar` and `SolarResult` with the same fields, defaults
  and units as `peakpilot/engine.py`, using only the standard library.
- R1.2 The single-diode I-V curve, NOCT cell temperature, golden-section true MPP and
  perturb-and-observe tracker SHALL follow the Python arithmetic order so results are bit-identical.
- R1.3 Both runs SHALL net the same PV series; the coordinated scheduler SHALL use base − PV for
  headroom and the water-heater forecast.
- R1.4 The JSON output SHALL carry a `"solar"` object, after `"coordinated"`, only when the scenario
  has solar.
- R1.5 The CLI SHALL list and run `sunny_evening`, and `--table` SHALL show PV energy and MPPT
  tracking efficiency when present.
- R1.6 `scripts/parity_check.py` SHALL cover `sunny_evening`, with random overrides, and report
  every case identical.

## R2 — Study S4: rooftop PV and MPPT (SIMULATED)

- R2.1 `studies/s4_solar_mppt.py` SHALL measure MPPT tracking efficiency across perturbation step
  sizes and iterations per minute, against the true MPP.
- R2.2 It SHALL measure how PV changes the uncoordinated peak, the scheduler's reactive floor and
  the LP lower bound, with and without solar, on the same workload.
- R2.3 It SHALL write `studies/results/s4_solar_mppt.json`; `tests/test_learn.py`-style tests SHALL
  reproduce its headline numbers.
- R2.4 The notebook SHALL gain an S4 section with a figure and findings, labeled SIMULATED, with no
  cost or emissions claims.
