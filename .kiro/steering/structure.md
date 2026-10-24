# PeakPilot — Structure Steering

## Repository layout

```
PeakPilot/
  app.py                  # Streamlit dashboard entry point
  peakpilot/
    __init__.py
    engine.py             # pure-stdlib simulation + least-slack-first scheduler
    scenarios.py          # named reproducible scenarios + Scenario dataclass
    massgis.py            # loads bundled MassGIS CSVs into typed rows
    optimal.py            # perfect-foresight LP peak benchmark (SciPy; lower bound) + reactive floor
    learn.py              # room-model calibration + forecast-error cost (SciPy; analysis only)
  data/
    utilities.csv         # MassGIS: electric utility by town (bundled snapshot)
    landfills.csv         # MassGIS: renewables at MA landfills (bundled snapshot)
    DATA.md               # provenance: source URLs, retrieval date, units, missing values, terms
  tests/
    test_engine.py        # energy accounting, limits, deadlines, infeasibility, reproducibility
    test_optimal.py       # LP bound <= coordinated peak, energy, comfort, limits, reproducibility
    test_learn.py         # Hypothesis properties + study reproduction for learn.py
  .kiro/
    specs/peakpilot/      # requirements.md, design.md, tasks.md (spec planning)
    specs/ml-models/      # ML spec; studies/ holds the research notebook, scripts, MATLAB cross-check
    steering/             # product.md, tech.md, structure.md
    KIRO_USAGE.md         # honest write-up of Kiro tools/features used
  docs/
    DEMO_SCRIPT.md        # <= 2:30 spoken demo script
    SUBMISSION_CHECKLIST.md
  requirements.txt
  README.md
  LICENSE
```

## Boundaries

- `peakpilot/engine.py` is the single source of truth for control logic. Nothing else
  reimplements scheduling. The dashboard imports and calls it.
- `engine.py` imports no third-party or UI libraries (stdlib only).
- `optimal.py` and `learn.py` are the only modules that import SciPy. They benchmark, calibrate
  and score a `Scenario` by calling the engine and the LP; they never schedule what the dashboard
  shows as PeakPilot's behavior, and no learned model makes a control decision.
- `.kiro/specs/*/studies/` is research run on the development machine. Nothing imports it at
  runtime, and it is outside the Raspberry Pi image's build context (`rust/peakpilot-core`).
- `massgis.py` reads only from bundled `data/*.csv`. No network calls at runtime.
- Every public function and dataclass carries a docstring stating units and assumptions.

## Naming

- Power: `*_kw`. Energy: `*_kwh`. Temperature: `*_c`. Time-of-day/step counts: minutes.
- Simulated values surfaced in the UI carry an explicit "SIMULATED" label.
- MassGIS-derived values surfaced in the UI carry a source + snapshot-date caption.
