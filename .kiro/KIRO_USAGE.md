# How Kiro was used to build PeakPilot

An honest account of which Kiro features were used, what they improved, and what was
deliberately not used. Written for the Hackachusetts "Kiro usage" submission field. Work
done by Claude Code instead of Kiro is listed separately at the end.

## Surfaces

Most of the build happened in the **Kiro IDE**. One dashboard UI review ran as a **Kiro CLI**
agent session (see chrome-devtools below).

## Spec-driven development (`.kiro/specs/`)

Kiro wrote four specs, each with `requirements.md`, `design.md` and `tasks.md`:

- `peakpilot`: core engine and dashboard
- `rust-engine`: Raspberry Pi port
- `test-framework`
- `optimal-benchmark`: LP lower bound

Every task traces back to a numbered requirement, and the scheduler's correctness
properties in the design docs became tests. Kiro also wrote `.kiro/steering/workflow.md`,
the issue → spec → branch → PR process every change followed.

Specs were used to check finished work, not only to plan it:

- **Task run with sub-agents.** Kiro's "run all tasks" mode gave each `peakpilot` task its
  own sub-agent, which checked the task against the code. Task 1.4 failed because the
  decision log repeated the same entries every minute (#25). A sub-agent fixed it in a git
  worktree, in both the Python and Rust engines (PR #27). Scheduling output stayed
  byte-identical.
- **Goal workflow.** A follow-up goal workflow checked tasks 1.5–3.6. It found that offline
  devices were not shown as OFFLINE in the status panel (#26, fixed in PR #28) and recorded
  the verified status of every task (PR #29; Claude Code ticked the last boxes in the same PR).

## Multi-agent workflow

One Kiro workflow run built the whole optimal-benchmark feature, each step in its own agent
session: set up a git worktree, open issue #9, write the spec, implement, review, then open
and merge PR #12. The review step checked the new panel in a browser on three scenarios and
saved screenshots and a verification report under `.agents/tasks/`.

## Steering (`.kiro/steering/`)

Four always-on steering docs held the project's non-negotiables, so they applied to every
edit without anyone having to remember them:

- **product.md**: the honesty rules (label SIMULATED, keep MassGIS facts separate, no
  cost/carbon claims, report infeasibility, same work in both runs). These shaped the
  infeasibility banner and the SIMULATED labels.
- **tech.md**: the engine stays pure standard library, results are deterministic, units are
  fixed, and SciPy is allowed only in `optimal.py` and `learn.py`.
- **structure.md**: repository layout and boundaries.
- **workflow.md**: how changes land.

## Agent hooks (`.kiro/hooks/`)

Kiro created all five hooks:

- A `UserPromptSubmit` hook that tells the agent to check current library docs in Context7
  before writing library code.
- A `PreToolUse` guard that asks before destructive shell commands (`rm`,
  `git reset --hard`, force push, overwriting redirects). It was tested against 18 sample
  commands.
- Two `PostFileSave` hooks for Mermaid. One sets the ELK layout and render-checks each
  diagram with mermaid-cli. The other adds a diagram where it clearly helps. This is why the
  README and design docs have working architecture and sequence diagrams.
- A `Stop` hook that removes worktrees under `.worktrees/` once their branch is merged. It
  never forces: it uses `git branch -d` and skips dirty worktrees, so the worktrees that
  workflows create don't pile up. (Claude Code committed the file in #23.)

## MCP servers and Powers

- **chrome-devtools:** before the first PR, Kiro opened the running Streamlit dashboard in a
  real browser, read the accessibility tree, confirmed zero console errors and took
  screenshots. Later a Kiro CLI session reviewed the UI at an 858 px viewport. It found
  deadline sliders that showed raw hours (17–32) and noisy AC entries in the log, opened
  issue #13, and fixed both in PR #14 (clock-time deadlines, AC cycling hidden in the log, a
  neutral energy delta, kW units).
- **GitHub:** Kiro created the tracking issues, opened PRs and merged them without leaving the
  editor.
- **Context7 MCP:** for the Rust port, Kiro checked the current proptest, serde, Docker and
  GitHub Actions docs before writing code.
- **Context7 Power:** installed through Kiro Powers and used to check Streamlit APIs, such as
  the replacement for the deprecated `use_container_width` and how `st.select_slider`
  formats values.

## Testing

- Kiro ran pytest inside the loop. It caught a CI failure (`ModuleNotFoundError`) and fixed
  it by adding `pyproject.toml` and an editable install.
- The `test-framework` spec added shared fixtures, a coverage gate, scenario and MassGIS
  tests, and a dashboard smoke test (PR #11).
- For the Rust port, Kiro wrote property-based tests (`proptest`, 256 generated scenarios per
  property) and a CI parity check that compares the full JSON output of both engines. It was
  104 of 104 identical when built (4 named scenarios plus 100 seeded variations) and is 130
  of 130 today, after the rooftop PV scenario was added.

The property tests found two real bugs that existed in both engines; both are fixed in both:

1. A task counted as "met" even when its energy arrived after its own deadline.
2. An offline device kept drawing power after it reached its target.

## What was deliberately NOT used, and why

- **ML-based control:** the scheduler is deterministic and explainable on purpose. That is
  the engineering contribution, and it is far easier to verify than a learned policy.
  Learned models appear only as analysis beside it (see below).
- **A test-on-save hook:** pytest already ran at every change, so the hooks do other jobs.

## Net effect

Specs planned the work and then checked it: sub-agents and a goal workflow found two real
defects (#25, #26) after the tasks looked done. Steering kept the honesty rules enforced
across the codebase. MCP let the same session verify the UI in a browser and run the GitHub
process, and property tests found two bugs shared by both engines.

## Built with Claude Code, not Kiro

**Attribution:** the following were written by Claude Code (Anthropic), not by Kiro:

- the ML studies spec (`.kiro/specs/ml-models/`), its studies and implementation (PRs #16–#18);
- the dashboard scenario fix (#21);
- rooftop PV with MPPT in both engines, its specs and study S4 (PRs #34, #36);
- moving the studies to `studies/` (#32) and the React frontend spec (`.kiro/specs/react-frontend/`);
- the submission docs.

Claude Code worked inside the structures Kiro had set up: Kiro's spec format (requirements →
design → tasks), the steering docs, and the issue → spec → branch → PR workflow. It also read
the earlier Kiro session logs for prior decisions. Kiro's hooks run only inside Kiro, so they
did not run during this work.

"Where could machine learning help, and is it measurable?" was answered with a spec before any
production code:

- **Studies first.** Three studies (top-level `studies/`, with an executed notebook) measured
  the benefit: the scheduler's reactive floor (7.8 kW vs a 6.03 kW perfect-foresight bound on
  Hot evening), room-model calibration (< 0.5 % parameter error from noisy SIMULATED
  telemetry), and what a wrong forecast costs a planner (a 2 °C cool bias breaks comfort for
  462 minutes). Earlier Kiro session logs were mined for prior decisions, which kept ML out of
  control and SciPy-only.
- **MATLAB as a cross-check, not a dependency.** MATLAB R2026b reproduces every fitted number
  to ~1e-8 and drives the Python engine through `pyenv`. It stays off the judge's path
  (licence) and out of the Raspberry Pi image.
- **Requirements → design → tasks** traced every task to an EARS-style requirement, and the
  spec's acceptance criteria became tests (`tests/test_learn.py`).
- **Property-based testing.** Hypothesis checks that calibration recovers *any* room in the
  parameter range from clean data (derandomized, so CI is repeatable). Fixed-example tests pin
  the study numbers. A wall-clock test that failed only under coverage tracing was caught here
  and split into a timing check plus a grid-size check.
- **Context7** (from Claude Code) was used to check the SciPy, Hypothesis and Streamlit 1.40.2
  APIs before coding.
