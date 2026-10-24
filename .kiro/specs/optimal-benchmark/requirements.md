# Optimal benchmark — Requirements

Issue: [#9](https://github.com/sohampatwardhan/PeakPilot/issues/9). Branch `feat/optimal-benchmark`.
Sized for a ~2 hour slot. Numbers below are local to this spec.

## Summary

Add a separate dashboard panel, "How close to optimal?", that compares the coordinated scheduler's
peak kW with the lowest peak a perfect-foresight linear program (LP) can reach for the same scenario.
The panel is separate from the uncoordinated-vs-coordinated comparison, not a third column in it.

## R1 — Benchmark model (`peakpilot/optimal.py`)

- R1.1 The benchmark SHALL minimize peak building kW (base load plus all devices) over the same 960
  one-minute steps, using the engine's `Scenario` and its parameters unchanged.
- R1.2 Each device with a `target_kwh` SHALL receive exactly that energy before its `deadline_min`.
- R1.3 Each device's power SHALL stay within `[0, max_kw]`.
- R1.4 WHILE a device is in its `offline_window`, its power SHALL hold the level of the minute before
  the window (0 if the window starts at minute 0), matching the engine's offline assumption.
- R1.5 The room temperature SHALL follow the engine's thermal model and stay at or below `comfort_c`
  at every recorded minute.
- R1.6 The benchmark SHALL NOT change `engine.py` or reimplement the scheduler.
- R1.7 Identical scenarios SHALL produce identical benchmark output.

## R2 — Honest framing

- R2.1 WHEN the LP relaxes an engine rule (on/off states, minimum run times), the result SHALL be
  labeled "lower bound on achievable peak" with the reason stated.
- R2.2 The panel SHALL state that the benchmark has perfect foresight of the whole evening.
- R2.3 WHEN the LP is infeasible, the panel SHALL say so plainly and SHALL NOT show a number.
- R2.4 WHEN the bound exceeds the power limit, the panel SHALL say the limit cannot be met even with
  perfect foresight.
- R2.5 WHEN the coordinated run missed a deadline or the comfort limit, the panel SHALL say the
  comparison is not like-for-like.
- R2.6 Simulated values SHALL carry the SIMULATED label. The panel SHALL make no cost or emissions claims.

## R3 — Panel content and performance

- R3.1 The panel SHALL show the coordinated peak kW, the bound, and the gap in kW and %.
- R3.2 The solve SHALL keep 1-minute resolution and SHALL be cached on the scenario inputs.
- R3.3 IF a solve takes more than ~2 s, the panel SHALL compute on a button press instead of on every rerun.

## R4 — Dependencies, tests, docs

- R4.1 `requirements.txt` SHALL pin `scipy==1.17.1`. Only `peakpilot/optimal.py` may import SciPy.
- R4.2 `tests/test_optimal.py` SHALL check, for every named scenario: bound ≤ coordinated peak,
  energy met by deadline, comfort limit held, power limits held, and reproducibility.
- R4.3 `pytest -q` SHALL stay green.
- R4.4 product.md, tech.md, structure.md, AGENTS.md and README SHALL be updated in this branch
  (ML-based control stays out of scope; `engine.py` stays stdlib-only).

## Acceptance criteria

1. Every named scenario solves with status `optimal` in under 2 s.
2. For every named scenario, bound ≤ coordinated peak + 1e-6 kW.
3. In each LP solution: per-device energy before the deadline equals `target_kwh` (±1e-6 kWh), power is
   0 at and after the deadline, room ≤ `comfort_c` + 1e-6 °C, and every power value is in `[0, max_kw]`.
4. Two solves of the same scenario give equal `to_json_dict()` output.
5. A scenario whose EV target exceeds `max_kw × deadline / 60` shows the infeasible message and no number.
6. The "Infeasible (8 kW)" scenario shows a bound above 8 kW and the "limit cannot be met" message.
7. CI's stdlib check still passes for `engine.py`, and `pytest -q` is green.

## Assumptions

- The engine enforces only an upper comfort limit, so the "comfort band" is `room_c ≤ comfort_c`.
  Adding a lower bound would constrain the LP more than the engine and break the lower-bound property.
- The power limit is not an LP constraint. Peak is the objective, and the limit is compared afterwards.

## Out of scope

MILP with on/off and minimum-run binaries, a chart of the LP schedule, using the LP as a controller,
ML-based control, and cost or carbon figures.
