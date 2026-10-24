# PeakPilot — submission checklist

Hackachusetts 2026 · Energy & climate tech · Challenge C3 (clean power at the peak).
Deadline: 8:00 PM Eastern, October 24, 2026.

## Required deliverables

- [x] Public GitHub repository with runnable source and dependency instructions
  → https://github.com/sohampatwardhan/PeakPilot
- [x] Root `.kiro/` committed (steering, specs, Kiro usage write-up)
- [x] README with setup, demo steps, assumptions, limitations, dataset attribution
- [x] Working application (Streamlit dashboard) — verified in-browser
- [x] Project description (features, intended users, value) — in README
- [x] Honest Kiro usage write-up → `.kiro/KIRO_USAGE.md`
- [x] Demo script targeting ≤2:30 → `docs/DEMO_SCRIPT.md`
- [ ] Demo video recorded, under 3:00 — **MANUAL** (record using the demo script)
- [ ] Public video URL — **MANUAL** (upload, then paste URL below)
- [ ] Idea submitted via the Hackachusetts form — **MANUAL** (do not auto-submit)

## Submission form fields (fill when submitting)

- **Team members:** Soham Patwardhan
- **Track:** Energy & climate tech (C3 — a more reliable clean energy system)
- **Repository URL:** https://github.com/sohampatwardhan/PeakPilot
- **Demo access:** run locally — `pip install -r requirements.txt && streamlit run app.py`
  (see README Quick start); the app needs no network or credentials.
- **Public video URL:** _<paste after upload>_

## Pre-submit verification

- [x] `pytest -q` green locally (11 passed)
- [ ] CI green on the PR — confirm the latest run on PR #4 is passing before merge
- [x] App launches and all four scenarios render without errors
- [x] SIMULATED labels present; MassGIS source + snapshot date shown; no cost/carbon claims

## Remaining manual steps (owner: Soham)

1. Confirm CI is green, then merge PR #4 into `main`.
2. Record the demo video (≤3:00) following `docs/DEMO_SCRIPT.md`.
3. Upload the video; make it public; paste the URL above and in the form.
4. Submit the idea via the Hackachusetts form. **Nothing auto-submits.**
