//! JSON output — the only module that uses serde.
//!
//! Serializes a [`CompareResult`] to exactly the key set produced by the Python
//! `CompareResult.to_json_dict()`, so the dashboard (or any other front end) can consume
//! either engine's output unchanged. The contract is pinned in `tests/golden/json_contract.json`.

use serde::ser::{Serialize, Serializer};

use crate::model::{clock, CompareResult, DecisionEntry, DeviceMap, RunResult};

/// Device maps serialize as JSON objects in insertion order (ev-1, wh-1, ac-1).
impl<T: Serialize> Serialize for DeviceMap<T> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_map(self.iter())
    }
}

#[derive(serde::Serialize)]
struct DecisionRow<'a> {
    time: String,
    device: &'a str,
    message: &'a str,
}

impl<'a> From<&'a DecisionEntry> for DecisionRow<'a> {
    fn from(d: &'a DecisionEntry) -> Self {
        DecisionRow {
            time: clock(d.minute),
            device: &d.device,
            message: &d.message,
        }
    }
}

#[derive(serde::Serialize)]
struct RunJson<'a> {
    label: &'a str,
    minutes: &'a [u32],
    clock: Vec<String>,
    total_kw: &'a [f64],
    per_device_kw: &'a DeviceMap<Vec<f64>>,
    room_c: &'a [f64],
    power_limit_kw: f64,
    peak_kw: f64,
    total_kwh: f64,
    per_device_kwh: &'a DeviceMap<f64>,
    tasks_met: &'a DeviceMap<bool>,
    unmet_kwh: &'a DeviceMap<f64>,
    minutes_over_limit: u32,
    temp_violation_min: u32,
    decision_log: Vec<DecisionRow<'a>>,
}

impl<'a> From<&'a RunResult> for RunJson<'a> {
    fn from(r: &'a RunResult) -> Self {
        RunJson {
            label: &r.label,
            minutes: &r.minutes,
            clock: r.minutes.iter().map(|&m| clock(m)).collect(),
            total_kw: &r.total_kw,
            per_device_kw: &r.per_device_kw,
            room_c: &r.room_c,
            power_limit_kw: r.power_limit_kw,
            peak_kw: r.peak_kw,
            total_kwh: r.total_kwh,
            per_device_kwh: &r.per_device_kwh,
            tasks_met: &r.tasks_met,
            unmet_kwh: &r.unmet_kwh,
            minutes_over_limit: r.minutes_over_limit,
            temp_violation_min: r.temp_violation_min,
            decision_log: r.decision_log.iter().map(DecisionRow::from).collect(),
        }
    }
}

#[derive(serde::Serialize)]
struct CompareJson<'a> {
    scenario_name: &'a str,
    power_limit_kw: f64,
    comfort_c: f64,
    peak_reduction_pct: f64,
    baseline: RunJson<'a>,
    coordinated: RunJson<'a>,
}

/// Serialize a comparison to JSON (compact, or pretty-printed when `pretty` is true).
pub fn to_json_string(result: &CompareResult, pretty: bool) -> serde_json::Result<String> {
    let view = CompareJson {
        scenario_name: &result.scenario_name,
        power_limit_kw: result.power_limit_kw,
        comfort_c: result.comfort_c,
        peak_reduction_pct: result.peak_reduction_pct(),
        baseline: RunJson::from(&result.baseline),
        coordinated: RunJson::from(&result.coordinated),
    };
    if pretty {
        serde_json::to_string_pretty(&view)
    } else {
        serde_json::to_string(&view)
    }
}
