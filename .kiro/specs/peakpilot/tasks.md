# PeakPilot — Tasks

Three increments, matching the build brief. Each task traces to requirements.

## Increment 1 — Correct simulation + baseline comparison

- [ ] 1.1 Engine data model: `DeviceSpec`, `DeviceState`, `Scenario`, `RunResult`, `CompareResult`
  with docstrings stating units. _Requirements: 1.2, 1.6, 4.1_
- [ ] 1.2 Thermal RC model + outdoor/base-load profiles. _Requirements: 1.1, 2.5_
- [ ] 1.3 Baseline run (full power when work remains, ignores limit). _Requirements: 1.4, 3.4_
- [ ] 1.4 Least-slack-first coordinated scheduler with min-run and AC priority. _Requirements: 2.1–2.6_
- [ ] 1.5 Metrics: peak kW, total/per-device kWh, tasks met, minutes over limit, temp violations,
  peak reduction %. _Requirements: 3.1, 3.3_
- [ ] 1.6 Offline-device handling (reserve last power, disclose). _Requirements: 4.2_
- [ ] 1.7 `scenarios.py` with named reproducible scenarios (hot evening, tight limit, EV offline,
  infeasible). _Requirements: 1.5_
- [ ] 1.8 pytest suite covering P1–P5. _Requirements: 1.3, 1.5, 2.1, 3.2, 3.4_

## Increment 2 — Interactive dashboard + scenario playback

- [ ] 2.1 Streamlit `app.py` skeleton importing the engine; sidebar controls. _Requirements: 5.1, 5.5_
- [ ] 2.2 Metric cards + before/after demand chart with limit line. _Requirements: 5.2, 5.3_
- [ ] 2.3 Room-temperature chart. _Requirements: 5.2_
- [ ] 2.4 Decision-log table + per-device status panel with OFFLINE/stale. _Requirements: 4.3, 5.4_
- [ ] 2.5 SIMULATED labels throughout; reset control. _Requirements: 5.5, 5.6_

## Increment 3 — MassGIS context, provenance, polish, submission

- [ ] 3.1 Bundle `data/utilities.csv` + `data/landfills.csv`; write `data/DATA.md` provenance. _Requirements: 6.3_
- [ ] 3.2 `massgis.py` loader returning typed rows (blanks preserved). _Requirements: 6.1, 6.2_
- [ ] 3.3 Town panel: utility + landfill projects, with source/date caption and honesty notes. _Requirements: 6.1, 6.2, 6.4_
- [ ] 3.4 `requirements.txt` (pinned), README demo steps/limitations/attribution. _Requirements: 7.1, 7.3_
- [ ] 3.5 `.kiro/KIRO_USAGE.md`, `docs/DEMO_SCRIPT.md` (≤2:30), `docs/SUBMISSION_CHECKLIST.md`. _Requirements: 7.2, 7.4_
- [ ] 3.6 Final verification run of tests + app smoke check; commit. _Requirements: 7.1_
