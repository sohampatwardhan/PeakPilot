# Rust Engine Port — Design

Diagram-rich design for porting PeakPilot's engine to Rust. Validates requirements in
`requirements.md`. The Python engine is the oracle; the Rust crate must match it.

## Component architecture

```mermaid
---
config:
  layout: elk
---
flowchart TB
    subgraph CRATE["peakpilot-core (Rust crate)"]
        direction TB
        MODEL["model.rs\nDeviceSpec, DeviceState,\nScenario, ThermalParams"]
        SCEN["scenarios.rs\nnamed reproducible scenarios"]
        ENGINE["engine.rs\nrun_baseline, run_coordinated,\ncompare -> CompareResult"]
        JSON["json.rs (serde)\nCompareResult -> JSON\n(matches to_json_dict)"]
        CLI["main.rs\nperakpilot run/list --table"]
    end
    SCEN --> ENGINE
    MODEL --> ENGINE
    MODEL --> SCEN
    ENGINE --> JSON
    ENGINE --> CLI
    JSON --> CLI

    CLI -->|"stdout JSON"| UI["Streamlit app.py\n(unchanged; shells out\nor reads JSON)"]
    CLI -->|"cross-compiled\naarch64 binary"| PI["Raspberry Pi /\nedge gateway"]
```

Only `std` is used in `model/scenarios/engine` (the control path). `serde`/`serde_json`
are confined to `json.rs` and the CLI boundary. _Validates: Requirements 2.1, 2.2, 3.1_

## Module responsibilities

| Rust module | Mirrors Python | Responsibility |
|---|---|---|
| `model.rs` | `engine.py` dataclasses | Device specs/state, `Scenario`, `ThermalParams`, `RunResult`, `CompareResult` |
| `scenarios.rs` | `scenarios.py` | The four named scenarios + a custom builder |
| `engine.rs` | `engine.py` functions | `run_baseline`, `run_coordinated`, `compare`, thermal step |
| `json.rs` | `to_json_dict()` | serde serialization matching the Python JSON shape |
| `main.rs` | (new) | CLI: `run`, `list`, `--table` |

## Data model (mirrors the Python engine)

```mermaid
classDiagram
    class Scenario {
        name: String
        power_limit_kw: f64
        base_load: Vec~f64~
        outdoor_c: Vec~f64~
        thermal: ThermalParams
    }
    class DeviceSpec {
        id: String
        kind: DeviceKind
        max_kw: f64
        min_run_min: u32
        target_kwh: Option~f64~
        deadline_min: Option~u32~
        offline_window: Option~(u32,u32)~
    }
    class DeviceState {
        power_kw: f64
        delivered_kwh: f64
        online: bool
        last_update_min: u32
        run_remaining_min: u32
    }
    class RunResult {
        peak_kw: f64
        total_kwh: f64
        per_device_kwh: Map
        tasks_met: Map
        minutes_over_limit: u32
        temp_violation_min: u32
    }
    class CompareResult {
        peak_reduction_pct: f64
    }
    Scenario "1" o-- "many" DeviceSpec
    DeviceSpec "1" --> "1" DeviceState
    CompareResult "1" --> "2" RunResult
```

_Validates: Requirements 1.1, 3.1_

## Scheduler — identical two-pass least-slack-first loop

```mermaid
---
config:
  layout: elk
---
flowchart TD
    START["New minute m"] --> ONLINE["Refresh online/offline"]
    ONLINE --> P1["Pass 1 — commit forced loads:\nbase, offline holds,\nAC priority, WH mid min-run"]
    P1 --> SORT["Pass 2 — sort flexible tasks\nby slack ascending"]
    SORT --> SLACK{"slack <= 0 ?"}
    SLACK -->|"yes"| FULL["Full power;\nlog breach if over limit"]
    SLACK -->|"no"| HEAD{"headroom left?"}
    HEAD -->|"no"| PAUSE["Pause / hold under limit"]
    HEAD -->|"yes"| FIT["EV throttle to headroom;\nWH start only if whole\nmin-run fits the limit"]
    FULL --> COMMIT["Commit power, log state changes"]
    PAUSE --> COMMIT
    FIT --> COMMIT
    COMMIT --> TEMP["Advance room temp (RC model)"]
    TEMP --> START
```

This is a line-for-line port of the Python algorithm; same ordering, same tie-breaks
(sort by `(slack, id)`), same minimum-run and start-gate rules. _Validates: Requirements 1.3, 7.1_

## Parity verification against the oracle

```mermaid
sequenceDiagram
    participant CI as CI / parity script
    participant RS as Rust binary (peakpilot run)
    participant PY as Python engine (compare)
    loop each named scenario
        CI->>RS: run --scenario X  (JSON out)
        CI->>PY: compare(scenario X).to_json_dict()
        CI->>CI: compare metrics within tolerance
        alt mismatch beyond tolerance
            CI-->>CI: FAIL (report which metric diverged)
        else within tolerance
            CI-->>CI: PASS
        end
    end
```

Tolerance is a documented absolute/relative epsilon on floating metrics; integer metrics
(minutes over limit, temperature-violation minutes, tasks met) must match exactly.
_Validates: Requirements 1.4, 6.1, 6.3_

## Floating-point parity risk

The main parity hazard is divergence between Python `float` and Rust `f64` accumulation
order. Mitigations:
- Keep the *same operation order* as Python (accumulate `delivered_kwh += power/60.0` per step).
- Compare metrics, not every raw sample, with a small epsilon (e.g. `1e-6` relative).
- Keep integer-valued metrics exact — they encode the honesty guarantees and must not drift.

_Validates: Requirements 1.4, 1.5_

## JSON contract

`json.rs` serializes `CompareResult` to the exact key set Python emits (`scenario_name`,
`power_limit_kw`, `comfort_c`, `peak_reduction_pct`, `baseline`, `coordinated`; each run with
`minutes`, `clock`, `total_kw`, `per_device_kw`, `room_c`, `power_limit_kw`, `peak_kw`,
`total_kwh`, `per_device_kwh`, `tasks_met`, `unmet_kwh`, `minutes_over_limit`,
`temp_violation_min`, `decision_log`). A golden JSON file pins the shape so either engine
drifting breaks CI. _Validates: Requirements 3.1, 3.2_

## Build & edge deployment

```mermaid
---
config:
  layout: elk
---
flowchart LR
    SRC["peakpilot-core source"] --> HOST["cargo build --release\n(host: aarch64-apple-darwin)"]
    SRC --> CROSS["cargo build --release\n--target aarch64-unknown-linux-gnu"]
    CROSS --> LINK{"cross-linker\navailable?"}
    LINK -->|"yes"| BIN["static ARM64 binary\nfor Raspberry Pi"]
    LINK -->|"no"| NOTE["document command +\nprerequisite honestly;\nbuild in CI container"]
    HOST --> TEST["cargo test + parity check"]
```

The `aarch64-unknown-linux-gnu` and `arm-unknown-linux-gnueabihf` targets are already
installed. Cross-linking from macOS needs an appropriate linker (e.g. a cross toolchain);
if unavailable locally, the ARM build is produced/verified in a Linux CI job and the exact
command + prerequisite are documented. We state honestly whether the binary was run on real
hardware. _Validates: Requirements 5.1, 5.2, 5.3_

## Dependencies (security note)

`serde` + `serde_json` are the only non-std crates — both are the de-facto standard Rust
serialization libraries, widely audited and actively maintained, pinned in `Cargo.toml`.
The control path (model/scenarios/engine) stays pure `std`, minimizing the edge attack
surface. No network access at runtime. _Validates: Requirements 2.1, 2.2_
