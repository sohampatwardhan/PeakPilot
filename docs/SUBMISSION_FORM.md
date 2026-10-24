# PeakPilot — submission form text (paste-ready)

Drafted from what is in the repository on `main`. The Kiro section follows Kiro's own
account of the build, checked against git history. The video URL is the only blank left.
Nothing here is submitted automatically.

## Team members

Soham Patwardhan

## Challenge track

Climate Tech — Energy & climate tech, challenge C3: "a more reliable clean energy system —
clean power still has to show up at the peak."

## Repository

https://github.com/sohampatwardhan/PeakPilot (public; `.kiro/` committed at the root)

## Testing instructions

Python 3.11+, no network or credentials needed (MassGIS data is bundled):

```
git clone https://github.com/sohampatwardhan/PeakPilot.git && cd PeakPilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Tests: `pip install -e ".[test]" -r requirements.txt && pytest -q --cov`.

## Video

_<paste the public YouTube/Vimeo URL after upload>_

## Description (features and functionality)

PeakPilot is a Massachusetts-aware building energy simulator that shows how coordinating
flexible electrical loads cuts a building's peak demand without cutting the work that has
to get done.

Simulated IoT devices (an EV charger, a water heater and an air conditioner) report power
and room temperature. A deterministic, least-slack-first controller decides each minute
which loads can wait and which can't, keeping the building under a power limit while still
meeting every charging and heating deadline and the room's comfort limit. The dashboard
runs the same evening twice. On a hot evening, uncoordinated loads peak at 19 kW and sit
over a 14 kW limit for three hours. PeakPilot holds 14 kW, a 26% lower peak, with zero
minutes over and every deadline met. Every control decision is logged in plain language.

How close to optimal? A perfect-foresight linear program (SciPy/HiGHS) gives a lower bound
of 6.0 kW. PeakPilot's lowest holdable limit is 7.8 kW. A forecast-error panel shows why
forecast-driven control is risky: a forecast 2 °C too cool breaks comfort for 7.7 hours.
A SciPy fit calibrates the room's thermal model from thermostat-style telemetry.

PeakPilot is honest by design. All device data is labeled SIMULATED, and infeasible
scenarios report minutes over the limit instead of hiding them. An offline charger is
handled visibly. Public MassGIS data (electric utility and landfill renewable projects
by town) is shown with its source and date, kept separate from the simulation. It makes
no cost or carbon claims. A Rust port of the engine builds as a Raspberry Pi image for
edge deployment.

## How Kiro was used

The full write-up is in `.kiro/KIRO_USAGE.md`. The text below is paste-ready for the form.
It credits only Kiro: the ML studies, rooftop PV/MPPT and these docs came from Claude Code,
which the Additional info field and `KIRO_USAGE.md` say.

**Surfaces.** Most of the build happened in the **Kiro IDE**. One dashboard UI review ran as
a **Kiro CLI** agent session.

**Spec-driven development.** Kiro wrote four specs under `.kiro/specs/`, each with
requirements, design and tasks:
- `peakpilot`: core engine and dashboard
- `rust-engine`: Raspberry Pi port
- `test-framework`
- `optimal-benchmark`: LP lower bound

Every task traces back to a numbered requirement. The scheduler's correctness properties in
the design docs became tests. Kiro also wrote `.kiro/steering/workflow.md`, the issue → spec
→ branch → PR process every change followed.

We also used specs to check finished work, not only to plan it:
- **Task run with sub-agents.** Kiro's "run all tasks" mode gave each `peakpilot` task its
  own sub-agent, which checked the task against the code. Task 1.4 failed because the
  decision log repeated the same entries every minute (issue #25). A sub-agent fixed it in a
  git worktree, in both the Python and Rust engines (PR #27). Scheduling output stayed
  byte-identical.
- **Goal workflow.** A follow-up goal workflow checked tasks 1.5–3.6. It found that offline
  devices were not shown as OFFLINE in the status panel (#26, fixed in PR #28), then
  recorded the verified status of each task (PR #29).

**Multi-agent workflows.** One Kiro workflow run built the whole optimal-benchmark feature.
Each step ran in its own agent session:
1. Set up a git worktree.
2. Open issue #9.
3. Write the spec.
4. Implement.
5. Review.
6. Open and merge PR #12.

The review step checked the new panel in a browser on three scenarios. It saved screenshots
and a verification report under `.agents/tasks/`.

**Steering docs.** Four always-on steering files held the project's non-negotiables, so they
applied to every edit without anyone having to remember them:
- `product.md`: the honesty rules (label SIMULATED, keep MassGIS facts separate, no
  cost/carbon claims, report infeasibility, same work in both runs). These shaped the
  infeasibility banner and the SIMULATED labels.
- `tech.md`: the engine stays pure standard library, results are deterministic, units are
  fixed, and SciPy is allowed in only two modules.
- `structure.md`: repository layout and boundaries.
- `workflow.md`: how changes land.

**Agent hooks.** Kiro created all five hooks in `.kiro/hooks/`:
- A `UserPromptSubmit` hook that tells the agent to check current library docs in Context7
  before writing library code.
- A `PreToolUse` guard that asks before destructive shell commands (`rm`,
  `git reset --hard`, force push, overwriting redirects). It was tested against 18 sample
  commands.
- Two `PostFileSave` hooks for Mermaid. One sets the ELK layout and render-checks each
  diagram with mermaid-cli. The other adds a diagram where it clearly helps. This is why the
  README and design docs have working architecture and sequence diagrams.
- A `Stop` hook that removes worktrees under `.worktrees/` once their branch is merged. It
  never forces: it uses `git branch -d` and skips dirty worktrees. It keeps the worktrees
  that workflows create from piling up.

**MCP servers and Powers.**
- **chrome-devtools:** Before the first PR, Kiro opened the running Streamlit dashboard in a
  real browser, read the accessibility tree, confirmed zero console errors and took
  screenshots. Later, a Kiro CLI session reviewed the UI at an 858 px viewport. It found
  deadline sliders that showed raw hours (17–32) and noisy AC entries in the log. It opened
  issue #13 and fixed both in PR #14 (clock-time deadlines, AC cycling hidden in the log, a
  neutral energy delta, kW units).
- **GitHub:** Kiro created the tracking issues, opened PRs and merged them without leaving
  the editor.
- **Context7 MCP:** For the Rust port, Kiro checked the current proptest, serde, Docker and
  GitHub Actions docs before writing code.
- **Context7 Power:** We installed the Context7 Power and used it through Kiro Powers to
  check Streamlit APIs, such as the replacement for the deprecated `use_container_width` and
  how `st.select_slider` formats values.

**Testing.**
- Kiro ran pytest inside the loop. It caught a CI failure (`ModuleNotFoundError`) and fixed
  it by adding `pyproject.toml` and an editable install.
- The `test-framework` spec added shared fixtures, a coverage gate, scenario and MassGIS
  tests, and a dashboard smoke test (PR #11).
- For the Rust port, Kiro wrote property-based tests (`proptest`, 256 generated scenarios per
  property). It also added a CI parity check that compares full JSON output from both
  engines: 104 of 104 runs identical when built (4 named scenarios plus 100 seeded
  variations), and 130 of 130 today after a fifth scenario was added.

The property tests found two real bugs that existed in both engines, and both are now fixed
in both:
1. A task counted as "met" even when its energy arrived after its own deadline.
2. An offline device kept drawing power after it reached its target.
