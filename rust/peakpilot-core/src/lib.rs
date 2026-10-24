//! PeakPilot control engine — edge-deployable Rust core.
//!
//! A behaviour-for-behaviour port of the Python engine in `peakpilot/engine.py`. It
//! simulates one building from 16:00 to 08:00 (the next day) in one-minute steps and runs
//! the same workload twice: an uncoordinated baseline and a coordinated least-slack-first
//! schedule that holds the building under a power limit.
//!
//! The control path (`model`, `scenarios`, `engine`) uses only the standard library.
//! `serde` is used solely in [`json`] and at the CLI boundary, never in the scheduler.
//!
//! All device telemetry is SIMULATED. Nothing here controls real electrical equipment.

pub mod engine;
pub mod json;
pub mod model;
pub mod scenarios;

pub use engine::{compare, py_sum, run_baseline, run_coordinated};
pub use model::{
    clock, CompareResult, DecisionEntry, DeviceKind, DeviceMap, DeviceSpec, DeviceState,
    RunResult, Scenario, ThermalParams, START_MINUTE, WINDOW_MINUTES,
};
