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
  data/
    utilities.csv         # MassGIS: electric utility by town (bundled snapshot)
    landfills.csv         # MassGIS: renewables at MA landfills (bundled snapshot)
    DATA.md               # provenance: source URLs, retrieval date, units, missing values, terms
  tests/
    test_engine.py        # energy accounting, limits, deadlines, infeasibility, reproducibility
  .kiro/
    specs/peakpilot/      # requirements.md, design.md, tasks.md (spec planning)
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
- `massgis.py` reads only from bundled `data/*.csv`. No network calls at runtime.
- Every public function and dataclass carries a docstring stating units and assumptions.

## Naming

- Power: `*_kw`. Energy: `*_kwh`. Temperature: `*_c`. Time-of-day/step counts: minutes.
- Simulated values surfaced in the UI carry an explicit "SIMULATED" label.
- MassGIS-derived values surfaced in the UI carry a source + snapshot-date caption.
