# Rust solar port + solar study — Tasks

Issue: [#35](https://github.com/sohampatwardhan/PeakPilot/issues/35). Ordered. Each task traces to `requirements.md`.

- [x] 1 Add `src/solar.rs` and wire `Scenario.solar` / `CompareResult.solar`. _Requirements: 1.1, 1.2_
- [x] 2 Net PV in `run_baseline` / `run_coordinated`; conditional `"solar"` JSON key. _Requirements: 1.3, 1.4_
- [x] 3 `sunny_evening` scenario, CLI table rows, Rust tests. _Requirements: 1.5_
- [x] 4 Python `custom_scenario(solar=...)`; parity table entry; run parity. _Requirements: 1.6_
- [x] 5 Write `studies/s4_solar_mppt.py`, run it, pin results in a test. _Requirements: 2.1–2.3_
- [x] 6 Notebook S4 section, executed. _Requirements: 2.4_
- [ ] 7 README / steering updates; `cargo clippy`, `cargo test`, `pytest`, parity; PR with `Closes #35`.
