# PeakPilot — submission form text (paste-ready)

Drafted from what is in the repository on `main`. Items marked **[confirm]** could not
be verified from the repo; check or edit them before pasting. Nothing here is submitted
automatically.

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

The full write-up is in `.kiro/KIRO_USAGE.md`. A short version for the form follows.

**Credit only what Kiro did.** The ML spec (`.kiro/specs/ml-models/`), its studies and
implementation (PRs #16–#18), the dashboard fix (#21) and these submission docs were written
by Claude Code, not Kiro. `KIRO_USAGE.md` says so. The judges score Kiro usage, so leave that
work out of the Kiro answer or name the tool that did it.

- **Tools:** **[confirm]** Kiro IDE, Kiro CLI and Kiro Crew. Local Kiro session logs exist
  for all three; say how they differed in your own words.
- **Spec-driven development:** Kiro specs under `.kiro/specs/`: `peakpilot`,
  `optimal-benchmark`, `rust-engine` and `test-framework`. Each has requirements, design and
  tasks, and tasks trace to requirements. Kiro also wrote `.kiro/steering/workflow.md`, the
  issue → spec → branch → PR process used for every change. **[confirm]** which of these
  specs Kiro wrote and which it only executed.
- **Steering:** four always-on docs. `product.md` holds the honesty rules: SIMULATED
  labels, MassGIS kept separate, no cost/carbon claims, report infeasibility, same work
  both runs. `tech.md` keeps the engine stdlib-only and says where SciPy may be used.
  `structure.md` covers layout and boundaries. `workflow.md` covers the change process.
- **Agent hooks:** five Kiro hooks in `.kiro/hooks/`. **[confirm]** that Kiro created each one.
  Git records who committed each file, not which tool wrote it, and the cleanup hook was
  committed by Claude Code in #23 from a file already in your checkout.
  - a Context7 docs reminder before library-specific work;
  - a guard that asks before destructive commands;
  - Mermaid layout and render validation;
  - a "Mermaid where appropriate" hook;
  - a Stop hook that removes worktrees once their branch merges.
- **MCP:** chrome-devtools (Kiro opened the running dashboard at an 858 px viewport, read
  the accessibility tree and checked the console; that review led to issue #13 and PR #14)
  and GitHub (issues and PRs). **[confirm]** whether Kiro itself called Context7, beyond
  the reminder hook.
- **Property-based testing:** Rust proptest runs 256-case engine properties in CI, and CI
  also checks Rust/Python output parity. **[confirm]** that Kiro wrote these. The Python
  Hypothesis tests in `tests/test_learn.py` came from Claude Code.
- **Kiro Powers:** **[confirm]** fill in if you used any; otherwise leave this bullet out.
