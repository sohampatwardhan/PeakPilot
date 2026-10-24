# Test Framework — Requirements

Tracks GitHub issue [#10](https://github.com/sohampatwardhan/PeakPilot/issues/10).

Only `peakpilot/engine.py` has tests today. `peakpilot/scenarios.py`, `peakpilot/massgis.py`
and the Streamlit dashboard (`app.py`) are untested, tests share no fixtures, and CI reports
no coverage. This change adds the missing structure and tests without changing runtime
behaviour.

## Requirements

### R1 — Shared test structure

**Story:** As a contributor, I want shared fixtures and registered markers so new tests are
short and consistent.

- R1.1 `tests/conftest.py` SHALL provide the repository root path, the scenario registry,
  and a fixture parametrized over every named scenario.
- R1.2 Custom markers SHALL be registered in `pyproject.toml`, and pytest SHALL run with
  `--strict-markers` so a mistyped marker fails.
- R1.3 Tests that need the dashboard dependencies SHALL carry the `dashboard` marker and
  SHALL be skipped (not failed) when Streamlit is not installed, so `pip install pytest`
  alone still runs the engine suite.

### R2 — Coverage in CI

- R2.1 `pytest-cov` SHALL be part of the `test` optional dependency.
- R2.2 Coverage configuration (source `peakpilot`, branch coverage, minimum threshold) SHALL
  live in `pyproject.toml`.
- R2.3 CI SHALL run the suite with coverage, print missing lines, and fail when total
  coverage of `peakpilot` falls below the threshold.

### R3 — Scenario tests

- R3.1 Every named scenario SHALL build a full 960-step window with the three expected
  devices and deadlines inside the window.
- R3.2 Builders SHALL be deterministic: two calls return equal scenarios.
- R3.3 All named scenarios SHALL share the same base-load profile, so differences between
  scenarios come only from the parameters each one sets.
- R3.4 `custom_scenario` overrides SHALL reach the built devices and limit.

### R4 — MassGIS loader tests

- R4.1 Row counts SHALL match `data/DATA.md` (351 towns, 116 landfill projects).
- R4.2 Lookups SHALL be case- and whitespace-insensitive; unknown towns return `None` / `[]`.
- R4.3 Empty `MW` / `SINCE` values SHALL load as `None`, never a guessed value.
- R4.4 Loading SHALL succeed with network access disabled.
- R4.5 The snapshot and retrieval dates in `massgis.py` SHALL match `data/DATA.md`.

### R5 — Dashboard smoke test

- R5.1 `app.py` SHALL render every named scenario headlessly (Streamlit `AppTest`) with no
  exceptions.
- R5.2 The rendered page SHALL label device data SIMULATED and show the MassGIS source and
  snapshot date, plus the "capacity is not generation" caveat.
- R5.3 The infeasible scenario SHALL show the honest-infeasibility warning; the feasible
  headline scenario SHALL report 0 minutes over the limit.

## Out of scope

Refactoring `tests/test_engine.py`, changing engine or dashboard behaviour, and Rust tests
(already covered by `.github/workflows/rust.yml`).
