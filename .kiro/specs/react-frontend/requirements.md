# React frontend — Requirements

Issue: [#20](https://github.com/sohampatwardhan/PeakPilot/issues/20). Branch `feat/react-frontend`.
**Scheduled for after the Hackachusetts submission (8:00 PM ET, 2026-10-24).** Numbers below are
local to this spec.

> **Status (added when committed, 2026-10-24):** a plan only; nothing here is implemented.
> - **Written by Claude Code, not Kiro.** A Claude Code session wrote this spec against `553dc04`.
> - **Out of date.** It predates the ML analysis panel (#18: reactive floor, forecast-error and
>   room-calibration expanders), the exact-scenario fix (#21), state-change-only decision logging
>   (#27) and the "Status at" offline panel (#28). Revise R1–R3 and the tasks for those before
>   implementing.
> - **Keep the code off `main` until judging ends.** The repository is part of the submission,
>   and the rules forbid changing a submission after the Submission Period. Build it on
>   `feat/react-frontend`.

## Summary

Add a React web frontend that shows the same comparison as the Streamlit dashboard, with results
that update live as the user changes inputs. Three pieces:

- a stdlib-only **presenter** that holds the view logic currently inline in `app.py`
- a thin **HTTP API** over the presenter, engine, benchmark and MassGIS loader
- a **`web/`** single-page app

The Streamlit dashboard stays as the submission app and the fallback. React is added alongside it
and does not replace it.

## R1 — Presenter (`peakpilot/presenter.py`)

- R1.1 The presenter SHALL import only the Python standard library and `peakpilot.engine`,
  `peakpilot.scenarios` and `peakpilot.massgis`. It SHALL NOT import `peakpilot.optimal`, because
  `Benchmark` already derives its own display flags.
- R1.2 The presenter SHALL publish each adjustable input with its default per named scenario, plus
  its minimum, maximum, step and unit. The inputs are the power limit, EV kWh, EV deadline,
  water-heater kWh and water-heater deadline. The ranges SHALL match the current dashboard: limit
  8–20 kW in 0.5 steps, EV 5–60 kWh, water heater 2–20 kWh, deadlines 17:00–08:00 on the hour.
- R1.3 The presenter SHALL build a `Scenario` from a scenario name plus overrides. It SHALL keep
  everything the overrides don't touch from the named scenario: outdoor temperature profile, base
  load, offline window, thermal parameters and note (see #19).
- R1.4 The presenter SHALL produce a view model with:
  - the metric cards: coordinated peak, baseline peak, peak reduction %, energy delivered with its
    deadline-task vs. AC split and delta text, minutes over limit with its delta, and deadlines met
  - the infeasibility messages
  - per-device status: kind, end power, online or OFFLINE/stale, last update clock time, commands
  - per-device delivered kWh and whether each task was met
  - the decision log, with each row flagged as AC cycling or not
- R1.5 The presenter SHALL NOT schedule, simulate, or change any engine or benchmark value. It
  only reads them and derives display fields.
- R1.6 `app.py` SHALL render from the presenter instead of computing these fields inline.

## R2 — HTTP API (`peakpilot/api.py`)

- R2.1 `GET /api/scenarios` SHALL return every named scenario with its note and its input
  defaults and ranges (R1.2).
- R2.2 `POST /api/compare` SHALL accept a scenario name and optional overrides. It SHALL return
  the engine's `CompareResult.to_json_dict()`, the `Benchmark.to_json_dict()`, the view model
  (R1.4) and a `diagnostics` object holding the solve time.
- R2.3 IF an override is outside its published range, or the scenario name is unknown, THEN the
  API SHALL respond 422 with a message naming the field. It SHALL NOT clamp the value silently.
- R2.4 `GET /api/massgis/towns` and `GET /api/massgis/{town}` SHALL return the town list, and for
  a town its utility and landfill projects, together with `SOURCE`, `PORTAL_SNAPSHOT_DATE` and
  `RETRIEVED_DATE`. An unknown town SHALL get a 404.
- R2.5 For identical requests, every response field except `diagnostics` SHALL be byte-identical.
- R2.6 The API SHALL make no outbound network calls. By default it SHALL bind to `127.0.0.1`.
- R2.7 The API SHALL NOT import or call the Rust engine. The Python engine stays the reference
  implementation.
- R2.8 WHEN `web/dist` exists, the API SHALL serve it at `/`, so one command runs the whole app.

## R3 — Web app (`web/`)

- R3.1 The web app SHALL show every panel the Streamlit dashboard shows: metric cards,
  infeasibility banner, demand chart with the power-limit line, room-temperature chart with the
  comfort line, "How close to optimal?" panel with all its states, decision log with the AC-cycling
  toggle (off by default), device status, per-device energy, and MassGIS context.
- R3.2 The web app SHALL render only server-provided values and view-model fields. It SHALL NOT
  compute peak, energy, deadline, infeasibility, comparability or status values itself.
- R3.3 WHEN an input changes, the web app SHALL request a new comparison after a short debounce,
  and SHALL throw away responses to superseded requests.
- R3.4 Input controls SHALL take their ranges and defaults from `GET /api/scenarios`. A "Reset to
  scenario defaults" control SHALL restore them.
- R3.5 WHILE a request is in flight, the web app SHALL keep the previous result on screen with a
  visible updating state. IF a request fails, THEN it SHALL show the error and SHALL NOT show stale
  numbers as current.
- R3.6 TypeScript types for API payloads SHALL be generated from the API's OpenAPI schema, not
  written by hand.
- R3.7 Controls SHALL be keyboard-operable with visible focus. The two runs SHALL be told apart by
  line style as well as color. Each chart SHALL have a text alternative stating its key values.

## R4 — Honesty labels

- R4.1 Every panel showing simulated values SHALL carry a visible **SIMULATED** label.
- R4.2 The MassGIS panel SHALL show the source and snapshot dates taken from the API response,
  and the warning that reported MW is capacity, not generation. It SHALL sit visually apart from
  the simulation panels.
- R4.3 The web app SHALL make no cost or emissions claims, and SHALL include the benchmark's
  "lower bound" and "perfect foresight" captions and its relaxations list.
- R4.4 WHEN the coordinated run exceeds the limit, breaks the comfort limit or leaves energy
  unmet, the infeasibility banner SHALL be shown, with the same messages as Streamlit.

## R5 — Dependencies, tests, CI, docs

- R5.1 New Python dependencies (FastAPI, Uvicorn, and httpx for tests) SHALL be pinned in
  `requirements.txt` and in a pyproject `api` extra. `engine.py` SHALL stay stdlib-only, and CI's
  third-party import check SHALL list `fastapi`.
- R5.2 Node dependencies SHALL be locked in `web/package-lock.json`. Node is needed only to build
  and test `web/`, not to run the Streamlit app or the Python tests.
- R5.3 pytest SHALL cover the presenter, the API (via a test client) and the OpenAPI snapshot.
  Coverage SHALL stay at or above the 90% `fail_under`.
- R5.4 Vitest with React Testing Library SHALL check that SIMULATED labels and MassGIS captions
  render, that the infeasibility banner appears for the "Infeasible" fixture, and that every
  benchmark state renders.
- R5.5 CI SHALL add a `web` job: `npm ci`, typecheck, test, build.
- R5.6 `tech.md`, `structure.md`, `product.md`, `AGENTS.md` and `README.md` SHALL be updated.
  The Raspberry Pi image's build context (`rust/peakpilot-core`) SHALL NOT change.

## Acceptance criteria

1. For every named scenario, the API's `view_model` numbers equal what `app.py` shows for the
   same inputs (both come from the presenter, and `tests/test_app.py` still passes).
2. `POST /api/compare` with `power_limit_kw: 25` returns 422 naming `power_limit_kw`.
3. Two identical `POST /api/compare` requests give equal bodies once `diagnostics` is removed.
4. The "Infeasible" scenario keeps its 34 °C outdoor peak through `build_scenario` with no overrides.
5. The OpenAPI snapshot test fails if `api.py` changes its schema without the snapshot being
   regenerated.
6. Vitest passes, including the label, banner and benchmark-state tests. `npm run build` succeeds.
7. `uvicorn peakpilot.api:app` with a built `web/dist` serves the full UI at `http://127.0.0.1:8000/`
   and works with networking off.
8. `pytest -q` is green with coverage at or above 90%, and CI's stdlib check for `engine.py` passes.

## Assumptions

- Single local user. No auth, no persistence, no multi-tenant concerns (product.md keeps auth out of scope).
- Compute is cheap (measured: compare ~4 ms, benchmark ~30 ms, payload ~180 KB raw / ~47 KB gzip),
  so the server recomputes on every request with no caching layer.
- The view is desktop-first. It must stay usable at tablet width (768 px). Phone layout is nice-to-have.

## Out of scope

Replacing or removing Streamlit, changing the demo script, a Rust/WASM in-browser engine,
Pyodide, charting the LP schedule, auth, deployment hosting, live data feeds, ML-based control,
and cost or carbon figures.
