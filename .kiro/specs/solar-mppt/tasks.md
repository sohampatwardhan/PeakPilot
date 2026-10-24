# On-site solar with MPPT — Tasks

Issue: [#33](https://github.com/sohampatwardhan/PeakPilot/issues/33). Ordered. Each task traces to `requirements.md`.

- [x] 1 Add `PVArray`, `Solar`, `SolarResult`, the I-V model, golden-section MPP, P&O tracker and
  `pv_kw_series()` to `engine.py`. _Requirements: 1.1–1.7_
- [x] 2 Subtract PV in `run_baseline` and `run_coordinated` (headroom and water-heater forecast); add
  `CompareResult.solar` and the conditional JSON key. _Requirements: 2.1–2.3_
- [x] 3 Add `clear_sky_irradiance()` and `sunny_evening()` to `scenarios.py` and the registry.
  _Requirements: 3.1, 3.2_
- [x] 4 Use net base load in `optimal.py`. _Requirements: 2.4_
- [x] 5 Write `tests/test_solar.py`; update registry-count tests. _Requirements: 1.4–1.7, 2.1–2.4_
- [x] 6 Dashboard: PV trace and solar metrics, labeled SIMULATED. _Requirements: 3.3_
- [x] 7 Update README, AGENTS.md layout and steering scope; note the Rust port as a follow-up.
  _Requirements: 3.4_
- [ ] 8 Run `pytest -q` and the parity check; open a PR with `Closes #33`. _Requirements: 2.3_
