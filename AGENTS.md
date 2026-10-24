# AGENTS.md — working in the PeakPilot repository

Guidance for AI agents and human contributors. PeakPilot is a Hackachusetts 2026
entry (Energy & climate tech, challenge C3). Read this before changing code.

## What this project is

A Massachusetts-aware building energy simulator that demonstrates IoT demand
coordination and makes the tradeoffs visible. It runs the same evening twice —
uncoordinated vs. coordinated — and compares peak demand, energy delivered,
deadlines met, and room comfort, with a plain-language decision log.

## Golden rules (do not violate)

1. **The engine is the single source of truth for control logic.** All scheduling
   lives in `peakpilot/engine.py`. The dashboard and any other front end import and
   call it; they never reimplement or fork the control loop.
2. **The engine is pure standard library.** `peakpilot/engine.py` imports nothing
   outside the Python stdlib. Keep it that way so it stays portable and testable.
3. **Honesty is a feature.** Simulated telemetry is always labeled SIMULATED. MassGIS
   facts are kept separate from simulation outputs. Never infer generation from
   installed capacity. Never claim cost or carbon savings. Report infeasibility
   (minutes over limit, temperature violations, unmet energy) instead of hiding it. A
   lower peak achieved by dropping required work is a failure, not a win.
4. **Determinism.** Identical `Scenario` inputs must produce identical results. No
   randomness in the control path.
5. **Same work both runs.** Baseline and coordinated runs use identical workloads,
   initial conditions, and environmental inputs.

The authoritative statements of these rules live in `.kiro/steering/` (product.md,
tech.md, structure.md). If this file and steering ever disagree, steering wins.

## Layout

```
app.py                 Streamlit dashboard (thin view over the engine)
peakpilot/engine.py    simulation + least-slack-first scheduler (stdlib only)
peakpilot/scenarios.py named reproducible scenarios + Scenario builder
peakpilot/massgis.py   loads bundled MassGIS CSVs (no runtime network)
peakpilot/optimal.py   perfect-foresight LP peak benchmark (SciPy; lower bound)
data/                  bundled MassGIS CSVs + DATA.md provenance
tests/                 pytest suite (engine correctness properties)
tests/test_optimal.py  LP benchmark properties (bound, energy, comfort, reproducibility)
.kiro/specs/peakpilot/ requirements.md, design.md, tasks.md
.kiro/steering/        always-on project rules
```

## Conventions

- Units: power `*_kw`, energy `*_kwh`, temperature `*_c`, time in minutes
  (minute 0 == 16:00). `energy_kwh = power_kw * minutes/60`.
- Every public function/dataclass carries a docstring stating units and assumptions.
- Comments explain contract and *why*, not mechanics.

## Build, run, test

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q            # engine correctness — must stay green
streamlit run app.py # dashboard
```

## Definition of done for a change

- `pytest -q` is green (CI enforces this on every push/PR).
- No new third-party import landed in `peakpilot/engine.py`.
- Any user-facing simulated value is labeled; any MassGIS value cites source + date.
- If behavior changed, the relevant test and the spec under `.kiro/specs/peakpilot/`
  were updated to match.
