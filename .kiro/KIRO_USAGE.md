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

## What was deliberately NOT used, and why

- **A heavy spec-workflow skill with per-gate approvals** — the hackathon has a hard same-day
  deadline, so the plain spec docs above were kept but the gated workflow was skipped to save time.
- **Context7 MCP** — the stack (Streamlit, pandas, plotly, stdlib) is stable and well-known;
  no live documentation lookups were needed, so none were added.
- **ML-based control** — the scheduler is deterministic and explainable on purpose; that is the
  engineering contribution and it is far easier to verify than a learned policy.
- **Hooks** — considered for auto-running tests on save, but pytest was already run manually at
  every change, so a hook would have added noise without benefit within the deadline.

## Net effect

Kiro's steering + specs kept the honesty rules enforced across the whole codebase; its MCP
integrations let the same session verify the UI in a browser and run the GitHub process
(issues + PR) without leaving the editor; and running tests inside the loop caught a real CI
packaging bug before merge.
