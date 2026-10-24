# Test Framework — Design

Tracks GitHub issue [#10](https://github.com/sohampatwardhan/PeakPilot/issues/10).
Requirements: `requirements.md`.

## Layout

| File | Covers | Needs |
|---|---|---|
| `tests/conftest.py` | shared fixtures: `repo_root`, `scenario_registry`, `named_scenario` (parametrized over every scenario) | stdlib |
| `tests/test_engine.py` | engine correctness properties (unchanged) | stdlib |
| `tests/test_scenarios.py` | scenario builders (R3) | stdlib |
| `tests/test_massgis.py` | bundled CSV loader (R4) | stdlib |
| `tests/test_app.py` | headless dashboard smoke test (R5), marked `dashboard` | `.[test]` + `requirements.txt` |

## Decisions

- **Coverage flags stay out of `addopts`.** `--cov` in `addopts` would break
  `pip install pytest && pytest -q`, which the README documents. Coverage settings live in
  `[tool.coverage.*]`; CI passes `--cov` explicitly.
- **Coverage measures `peakpilot` only.** `app.py` is exercised by the smoke test but is a
  view, so its line count would make the threshold noisy. Threshold: 90% (branch coverage).
- **Dashboard tests skip without Streamlit.** `pytest.importorskip` at module level, so an
  engine-only install still runs green.
- **`AppTest` uses an absolute script path and a 30 s timeout.** The default 3 s timeout is
  too short for the first run, which imports pandas and Plotly.
- **Network check monkeypatches `socket.socket.connect`** to raise, then clears the
  `lru_cache` on the loaders and reloads. Any network call fails the test.
- **`--strict-markers`** in `addopts` so a mistyped marker fails instead of silently
  creating a new one.

## CI

`.github/workflows/ci.yml` keeps its install step (it already installs `.[test]` and
`requirements.txt`) and changes the test step to
`pytest -q --cov --cov-report=term-missing`. `fail_under` in `pyproject.toml` makes the
step fail below 90%.
