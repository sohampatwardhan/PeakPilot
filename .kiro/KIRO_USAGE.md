# How Kiro was used to build PeakPilot

An honest account of which Kiro features were used, what they improved, and what was
deliberately not used. Written for the Hackachusetts "Kiro usage" submission field.

## Spec-driven planning (`.kiro/specs/peakpilot/`)

Before writing code, the work was framed as concise `requirements.md`, `design.md`, and
`tasks.md` under `.kiro/specs/peakpilot/`. These are plain, self-contained documents:
numbered requirements (R1–R7), a design with a least-slack-first scheduler and correctness
properties, and a three-increment task list. They kept the build scoped and gave every
commit something to trace back to. (A heavier spec-workflow skill was intentionally *not*
used — see below.)

## Steering (`.kiro/steering/`)

Three always-on steering docs encoded the project's non-negotiables so every edit stayed
consistent:
- **product.md** — the honesty rules (label SIMULATED, keep MassGIS separate, no cost/carbon
  claims, report infeasibility, same work both runs).
- **tech.md** — stack (Python stdlib engine + Streamlit), units, determinism, engine/UI separation.
- **structure.md** — repository layout and naming.

Benefit: the honesty constraints were applied automatically rather than remembered ad hoc.
They directly shaped the "honest infeasibility" banner and the SIMULATED labels.

## Agents & tools

- **AGENTS.md** at the repo root restates the golden rules for any future agent or human.
- **chrome-devtools MCP** was used to launch the running Streamlit app in a real browser,
  take an accessibility snapshot, confirm zero console errors, and screenshot the dashboard.
  This turned "it probably renders" into verified evidence.
- **GitHub MCP** drove the full GitHub workflow from inside the IDE: it authenticated the
  account, created three tracking issues (one per increment), and opened the pull request.
- **Terminal + pytest**: the engine was verified continuously (11 tests). A CI failure
  (`ModuleNotFoundError`) was diagnosed and fixed by adding `pyproject.toml` and an editable
  install — caught by Kiro running the tests, not guessed.

## ML studies spec (`.kiro/specs/ml-models/`)

"Where could machine learning help, and is it measurable?" was answered with a spec before any
production code:

- **Studies first.** Three studies (`studies/`, with an executed notebook) measured the benefit:
  the scheduler's reactive floor (7.8 kW vs a 6.03 kW perfect-foresight bound on Hot evening),
  room-model calibration (< 0.5 % parameter error from noisy SIMULATED telemetry), and what a
  wrong forecast costs a planner (a 2 °C cool bias breaks comfort for 462 minutes). Earlier
  Kiro session logs were mined for prior decisions, which kept ML out of control and SciPy-only.
- **MATLAB as a cross-check, not a dependency.** MATLAB R2026b reproduces every fitted number to
  ~1e-8 and drives the Python engine through `pyenv`. It stays off the judge's path (licence)
  and out of the Raspberry Pi image.
- **Requirements → design → tasks** traced every task to an EARS-style requirement, and the
  spec's acceptance criteria became tests (`tests/test_learn.py`, `tests/test_optimal.py`).
- **Property-based testing.** Hypothesis checks that calibration recovers *any* room in the
  parameter range from clean data (derandomized, so CI is repeatable). Fixed-example tests pin
  the study numbers. A wall-clock test that failed only under coverage tracing was caught here
  and split into a timing check plus a grid-size check.
- **Context7** was used to check the SciPy, Hypothesis and Streamlit 1.40.2 APIs before coding.

## What was deliberately NOT used, and why

- **A heavy spec-workflow skill with per-gate approvals** — the hackathon has a hard same-day
  deadline, so the plain spec docs above were kept but the gated workflow was skipped to save time.
- **ML-based control** — the scheduler is deterministic and explainable on purpose; that is the
  engineering contribution and it is far easier to verify than a learned policy. Learned models
  appear only as analysis beside it (see the ML studies spec above).
- **A test-on-save hook** — pytest was already run at every change. The hooks that were added
  (`.kiro/hooks/`) do other jobs: a Context7 docs reminder, a destructive-command guard, and
  Mermaid diagram layout and validation.

## Net effect

Kiro's steering + specs kept the honesty rules enforced across the whole codebase; its MCP
integrations let the same session verify the UI in a browser and run the GitHub process
(issues + PR) without leaving the editor; and running tests inside the loop caught a real CI
packaging bug before merge.
