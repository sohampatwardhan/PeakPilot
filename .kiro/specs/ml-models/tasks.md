# ML models (SciPy and MATLAB) — Tasks

Issue: [#15](https://github.com/sohampatwardhan/PeakPilot/issues/15). Ordered. Each task traces to `requirements.md`. Tasks 0–1 (the studies) are done in this
branch. The rest are the implementation plan.

- [x] 0 Open the GitHub issue (problem, the three findings, acceptance criteria) and put its number at the top of
  all three spec files. _Workflow steering_
- [x] 1 Run the studies and commit them as evidence: `studies/s1_thermal_id.py`, `studies/s2_forecast_value.py`,
  `studies/s3_matlab_parity.m`, `studies/results/*`, and the executed `studies/ml_studies.ipynb` with pinned
  `studies/requirements.txt`. _Requirements: Summary, 5.1_
- [x] 2 After PR #14 merges, bring `feat/ml-models` up to date with `main` (merged `5f234a3`, no force push).
  _Design: Risks_
- [x] 3 Add `ReactiveFloor` and `reactive_floor()` to `optimal.py` (full-grid scan, `monotone` flag), and add
  `floor`, `headroom_kw` and `headroom_pct` to `Benchmark`. Measure the time for every named scenario.
  _Requirements: 1.1–1.3, 1.5_
- [x] 4 Add `reactive_floor` tests to `tests/test_optimal.py`: Hot evening 7.8, EV offline 14.9 not monotone,
  Infeasible 11.7, and an unreachable deadline returning `None`. _Requirements: 6.2_
- [x] 5 Create `peakpilot/learn.py`: `fit_thermal` (EE seed → OE `least_squares`), `simulated_telemetry`, the
  `ThermalFit` mapping back to `ThermalParams`, and `ValueError` validation. Check the `least_squares` /
  `lstsq` APIs against Context7 `/scipy/scipy`. _Requirements: 2.1–2.4_
- [x] 6 Add `ForecastError`, `ForecastCost` and `forecast_cost()` to `learn.py`, reusing `optimal.solve`.
  _Requirements: 3.1, 3.2_
- [x] 7 Write `tests/test_learn.py`: Hypothesis property for recovery, `ValueError` cases, determinism, and
  reproduction of the S1 row and the S2 Part A table. Add `hypothesis` to the `test` extra. _Requirements: 6.1,
  6.3; AC 3, 4_
- [x] 8 Checkpoint: `pytest -q --cov` green, coverage ≥ 90 %, and `git diff main -- peakpilot/engine.py` empty.
  _Requirements: 4.2, 6.4_
- [x] 9 `app.py`: reactive-floor metrics row with the R1.2/R1.3 notes; the "What if the forecast is wrong?"
  expander; the "Calibrate the room model" expander with the use-calibrated toggle. Cache each with
  `hash_funcs`. Check `st.expander` / `st.toggle` against Context7 `/streamlit/docs` for 1.40.2.
  _Requirements: 1.4, 2.5, 2.6, 3.3–3.5, 4.1_
- [x] 10 Extend `tests/test_app.py` for the new panel elements. Smoke-test `streamlit run app.py` on all four
  scenarios with chrome-devtools at 858 px. _Requirements: 6.4; AC 1, 2_ (Done: real browser on Hot evening at
  858 px with the forecast and calibration expanders open, 0 console errors; all four scenarios headless via AppTest.)
- [x] 11 Update steering (product.md In list; tech.md and structure.md "SciPy in `optimal.py` and `learn.py`"),
  AGENTS.md, the README, and `.kiro/KIRO_USAGE.md` (studies, MATLAB cross-check, PBT). Add a DEMO_SCRIPT line only
  if it stays within 2:30. _Requirements: 4.3, 4.4, 5.2_ (DEMO_SCRIPT left unchanged.)
- [x] 12 Run `pytest -q --cov` once more, commit, and open a PR with `Closes #15`, the study headline numbers
  and the test results. Merge only with the user's go-ahead. _Requirements: 6.4_ (PR #18.)

## Follow-ups (separate issues, not this spec)

- EV-offline: the scheduler does not plan ahead for a known outage, so feasibility is not monotone in the limit
  (design.md, "Finding outside this feature").
- Dashboard: `app.py` rebuilds every scenario through `custom_scenario()` without `peak_outdoor_c`, so the
  "Infeasible" scenario runs at 31 °C in the app instead of its 34 °C (found during task 10; predates this spec).
- CSV upload of real thermostat telemetry for `fit_thermal`.
- Forecast-driven control (MPC with the reactive engine as a safety layer). This needs a steering change first.
