# Optimal benchmark — Tasks

Issue: [#9](https://github.com/sohampatwardhan/PeakPilot/issues/9). Ordered. Each task traces to `requirements.md`.

- [ ] 1 Pin `scipy==1.17.1` in `requirements.txt` and the pyproject `dashboard` extra. Add `"scipy"` to
  CI's third-party check for `engine.py`. _Requirements: 4.1_
- [ ] 2 Write `optimal.solve()` (LP build plus `linprog(method="highs")`), then **measure solve time**
  for every named scenario. If any solve takes more than 2 s, switch task 6 to the button design. Check the
  `linprog` and sparse APIs against Context7 `/scipy/scipy`. _Requirements: 1.1–1.5, 3.2, 3.3_
- [ ] 3 Add `OptimalResult`, `RELAXATIONS`, status mapping, input validation (`ValueError`), and
  `to_json_dict()` without `solve_time_s`. _Requirements: 1.7, 2.1, 2.3_
- [ ] 4 Add `benchmark()` and `Benchmark` (gap kW and %, `limit_achievable`, `coordinated_comparable`).
  _Requirements: 2.4, 2.5, 3.1_
- [ ] 5 Write `tests/test_optimal.py` per the design test plan and get `pytest -q` green.
  _Requirements: 1.2–1.5, 1.7, 2.3, 4.2, 4.3_
- [ ] 6 Add the "How close to optimal?" panel to `app.py`: a separate bordered container, SIMULATED labels,
  perfect-foresight and lower-bound captions, infeasible, limit, and not-like-for-like messages,
  and `st.cache_data` keyed on `Scenario` via `hash_funcs`. Check against Context7 `/streamlit/docs`
  for 1.40.2. _Requirements: 2.1–2.6, 3.1–3.3_
- [ ] 7 Smoke-test `streamlit run app.py` on all four scenarios plus one custom infeasible LP case.
  _Requirements: 2.3, 3.1_
- [ ] 8 Update product.md (In: benchmark; Out: ML control), tech.md (SciPy only in `optimal.py`),
  structure.md, AGENTS.md, and the README section. Add a DEMO_SCRIPT sentence only if the script stays
  within 2:30. _Requirements: 4.4_
- [ ] 9 Run `pytest -q` one last time and commit, then open a PR with `Closes #9` and the test results.
  _Requirements: 4.3_
