# React frontend — Tasks

Issue: [#20](https://github.com/sohampatwardhan/PeakPilot/issues/20). Ordered. Each task traces to `requirements.md`.
**Do not start before the submission deadline (8:00 PM ET, 2026-10-24) has passed.** Branch
`feat/react-frontend` from `main` after #19 is resolved or explicitly folded in (see task 1).

## Phase 1 — Presenter (Streamlit keeps working at every step)

- [ ] 1 Check whether #19 is merged. If it is, port its fix into `build_scenario`. If it isn't,
  fix it here and add `Closes #19` to the PR. _Requirements: 1.3_
- [ ] 2 Write `peakpilot/presenter.py`: `InputSpec`, `input_specs`, `build_scenario`,
  `validate_overrides`, `is_ac_cycling`, `massgis_context`, with docstrings stating units.
  _Requirements: 1.1–1.3_
- [ ] 3 Add `view_model()` by moving the derived logic out of `app.py` (energy split and delta text,
  infeasibility messages, device status and last update, AC-cycling flag). _Requirements: 1.4, 1.5_
- [ ] 4 Write `tests/test_presenter.py` for P1–P3, delta-text branches, infeasible messages and
  offline-EV status. _Requirements: 1.2–1.5, 5.3_
- [ ] 5 Move `app.py` onto the presenter (scenario build, sidebar ranges and defaults, metrics,
  banner, device tables, log filter). `tests/test_app.py` must pass unchanged. Checkpoint: run
  `pytest -q` and `streamlit run app.py` across all four scenarios. _Requirements: 1.6_

## Phase 2 — API

- [ ] 6 Pin FastAPI, Uvicorn and httpx in `requirements.txt` and in a pyproject `api` extra,
  choosing current stable versions via Context7 and PyPI. Add `"fastapi"` to CI's `engine.py`
  import check. _Requirements: 5.1_
- [ ] 7 Write `peakpilot/api.py`: Pydantic request and response models, the four `/api` endpoints,
  422/404 mapping, GZip, dev-only CORS, the `web/dist` static mount, and `--dump-openapi`. Check the
  FastAPI and Starlette APIs against Context7. _Requirements: 2.1–2.8_
- [ ] 8 Write `tests/test_api.py` for every endpoint, P4 (no clamping), P5 (determinism), P6 (OpenAPI
  snapshot against `web/openapi.json`), error bodies, gzip and the static mount.
  _Requirements: 2.1–2.6, 2.8, 5.3_
- [ ] 9 Add `scripts/dump_web_fixtures.py` (writes `web/src/test/fixtures/*.json`, with `--check`
  mode) and `tests/test_web_fixtures.py`. Checkpoint: `pytest -q` green, coverage ≥ 90%.
  _Requirements: 5.3_

## Phase 3 — Web app

- [ ] 10 Scaffold `web/` with Vite (React + TypeScript template), Vitest, React Testing Library,
  Recharts and openapi-typescript. Add the `gen:types`, `typecheck`, `test`, `build` and `dev`
  scripts, the `/api` dev proxy, and a committed `package-lock.json`. Check Vite, React and Recharts
  usage against Context7. _Requirements: 3.6, 5.2_
- [ ] 11 Write `api/client.ts` and the hooks `useScenarios`, `useComparison` (150 ms debounce,
  AbortController, updating and error states) and `useMassgis`. _Requirements: 3.3–3.5_
- [ ] 12 Build `Controls` (scenario picker, sliders and deadline selects from `InputSpec`, reset,
  town picker), keyboard-operable with visible focus. _Requirements: 3.4, 3.7_
- [ ] 13 Build `SimulatedBadge`, `MetricCards`, `InfeasibilityBanner`, `DeviceStatus` and
  `DecisionLog` (AC-cycling toggle off by default). Use the formatting table from the design.
  _Requirements: 3.1, 3.2, 4.1, 4.4_
- [ ] 14 Build `DemandChart` and `TemperatureChart` (reference lines, line-style distinction,
  hidden text summary) and `BenchmarkPanel` (all five states, captions, relaxations list).
  _Requirements: 3.1, 3.7, 4.3_
- [ ] 15 Build `MassGisPanel`, placed after a divider, with source, dates and caveat taken from the
  API. _Requirements: 4.2_
- [ ] 16 Write the Vitest suites: P7 labels, infeasibility banner, every benchmark state,
  AC-cycling toggle, reset, superseded responses ignored. _Requirements: 5.4_

## Phase 4 — CI, docs, verification

- [ ] 17 Add the CI `web` job (`npm ci`, `gen:types` + `git diff --exit-code`, typecheck, test,
  build). Leave `rust.yml` and the Pi image job untouched. _Requirements: 5.5, 5.6_
- [ ] 18 Update `tech.md`, `structure.md`, `product.md`, `AGENTS.md` and the README "React UI
  (optional)" section. _Requirements: 5.6_
- [ ] 19 Manual verification: all three serving modes, the four scenarios side by side with
  Streamlit (same numbers and states), networking off, tablet width, keyboard-only pass.
  _Requirements: 2.6, 2.8, 3.1, 3.7; acceptance 1, 7_
- [ ] 20 Run `pytest -q` and `npm --prefix web test` one last time, then commit and open a PR with
  `Closes #20` (plus `Closes #19` if task 1 folded it in) and the test results. _Requirements: 5.3–5.5_
