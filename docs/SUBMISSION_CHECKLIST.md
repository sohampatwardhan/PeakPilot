# PeakPilot — submission checklist

Hackachusetts 2026 · Climate Tech (Energy & climate tech) · Challenge C3 (clean power at the peak).
Deadline: 8:00 PM Eastern, October 24, 2026.

## Required deliverables

- [x] Public GitHub repository with runnable source and dependency instructions
  → https://github.com/sohampatwardhan/PeakPilot
- [x] Root `.kiro/` committed: steering, five specs, five hooks, CLI settings, Kiro usage write-up
- [x] README with setup, demo steps, assumptions, limitations, dataset attribution
- [x] Working application (Streamlit dashboard), verified in a browser
- [x] Project description: paste-ready in `docs/SUBMISSION_FORM.md`
- [x] Kiro usage write-up: `.kiro/KIRO_USAGE.md`; short form text in `docs/SUBMISSION_FORM.md`.
  Resolve every **[confirm]** there before pasting.
- [x] Demo script, about 2:30 including the "How close to optimal?" panel → `docs/DEMO_SCRIPT.md`
- [ ] Demo video recorded, under 3:00. **MANUAL**: record it from the demo script.
- [ ] Public video URL. **MANUAL**: upload to YouTube or Vimeo, make it public, paste the URL
  below and in `docs/SUBMISSION_FORM.md`.
- [ ] Submission form sent. **MANUAL**: nothing is submitted automatically.

## Submission form fields

Paste-ready text for every field is in `docs/SUBMISSION_FORM.md`.

- **Team members:** Soham Patwardhan
- **Track:** Climate Tech (Energy & climate tech, C3: a more reliable clean energy system)
- **Repository URL:** https://github.com/sohampatwardhan/PeakPilot
- **Demo access:** run locally with `pip install -r requirements.txt && streamlit run app.py`
  (see README Quick start). The app needs no network or credentials.
- **Public video URL:** _<paste after upload>_

## Pre-submit verification (on `main` at 6438081)

- [x] `pytest -q`: 144 passed locally
- [x] CI green on `main`: pytest 3.11/3.12, Rust tests + parity, and the Raspberry Pi image
- [x] No open pull requests. #18, #21 and #23 are merged.
- [x] All four scenarios render without errors. With default sliders the dashboard matches the
  scenario module exactly (#19).
- [x] SIMULATED labels present; MassGIS source and snapshot date shown; no cost/carbon claims
- [x] Tool attribution in `.kiro/KIRO_USAGE.md` separates Kiro's work from Claude Code's

## Remaining manual steps (owner: Soham)

1. Rehearse the click sequence in `docs/DEMO_SCRIPT.md`, then record the video (under 3:00).
2. Upload the video, make it public, and paste the URL above and in the form doc.
3. Resolve the **[confirm]** items in `docs/SUBMISSION_FORM.md`.
4. Fill in and submit the Hackachusetts form before 8:00 PM Eastern.
