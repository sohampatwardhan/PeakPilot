//! Data model for the PeakPilot engine (pure standard library).
//!
//! Mirrors the dataclasses in `peakpilot/engine.py`. Units: power in kW (`*_kw`), energy in
//! kWh (`*_kwh`), temperature in °C (`*_c`), and time in minutes from the window start
//! (minute 0 == 16:00). Every value produced from this model is SIMULATED.

/// Window start as minutes past midnight (16:00).
pub const START_MINUTE: u32 = 16 * 60;

/// Number of one-minute steps from 16:00 to 08:00 the next day.
pub const WINDOW_MINUTES: usize = 16 * 60;

/// Wall-clock `HH:MM` label for a step offset into the window.
///
/// Wraps past midnight, so step 480 reads `00:00`. Matches the Python `clock()`.
pub fn clock(step_min: u32) -> String {
    let absolute = (START_MINUTE + step_min) % (24 * 60);
    format!("{:02}:{:02}", absolute / 60, absolute % 60)
}

/// The three flexible loads PeakPilot coordinates.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeviceKind {
    Ev,
    WaterHeater,
    AirConditioner,
}

impl DeviceKind {
    /// Same string values as the Python `DeviceKind` enum.
    pub fn as_str(self) -> &'static str {
        match self {
            DeviceKind::Ev => "ev",
            DeviceKind::WaterHeater => "water_heater",
            DeviceKind::AirConditioner => "air_conditioner",
        }
    }

    /// EV and water heater owe energy by a deadline; the AC is driven by the thermal model.
    pub fn is_energy_task(self) -> bool {
        matches!(self, DeviceKind::Ev | DeviceKind::WaterHeater)
    }
}

/// Static configuration for one simulated device.
#[derive(Debug, Clone, PartialEq)]
pub struct DeviceSpec {
    /// Stable identifier, e.g. `"ev-1"`.
    pub id: String,
    pub kind: DeviceKind,
    /// Maximum power draw in kW.
    pub max_kw: f64,
    /// Once switched on, the device stays on at least this many minutes (0 = throttleable).
    pub min_run_min: u32,
    /// Energy owed before `deadline_min` (EV, water heater). `None` for the AC.
    pub target_kwh: Option<f64>,
    /// Minute by which `target_kwh` must be met. `None` for the AC.
    pub deadline_min: Option<u32>,
    /// Optional `[start, end)` minutes during which the device is offline and uncommandable.
    pub offline_window: Option<(u32, u32)>,
    /// Supported control commands, surfaced to a UI or a future real device driver.
    pub commands: Vec<&'static str>,
}

impl DeviceSpec {
    /// Whether the device is reachable at `step_min` (SIMULATED).
    pub fn is_online_at(&self, step_min: u32) -> bool {
        match self.offline_window {
            None => true,
            Some((start, end)) => !(start <= step_min && step_min < end),
        }
    }
}

/// Mutable per-minute runtime state for a device (all values SIMULATED).
#[derive(Debug, Clone, PartialEq)]
pub struct DeviceState {
    pub spec: DeviceSpec,
    pub power_kw: f64,
    pub delivered_kwh: f64,
    pub online: bool,
    pub last_update_min: u32,
    /// Minimum-run lock countdown in minutes.
    pub run_remaining_min: u32,
}

impl DeviceState {
    /// Fresh state: off, nothing delivered, online, no min-run lock.
    pub fn new(spec: DeviceSpec) -> Self {
        DeviceState {
            spec,
            power_kw: 0.0,
            delivered_kwh: 0.0,
            online: true,
            last_update_min: 0,
            run_remaining_min: 0,
        }
    }

    /// Energy still owed before the deadline (0 for the AC and once the target is met).
    pub fn remaining_kwh(&self) -> f64 {
        match self.spec.target_kwh {
            None => 0.0,
            // Written as Python's `max(0.0, x)` (returns 0.0 unless x > 0.0).
            Some(target) => {
                let x = target - self.delivered_kwh;
                if x > 0.0 {
                    x
                } else {
                    0.0
                }
            }
        }
    }
}

/// First-order RC room model parameters (illustrative, not a calibrated building).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ThermalParams {
    /// Thermal resistance (°C per kW of heat flow).
    pub r: f64,
    /// Thermal capacitance (kWh per °C).
    pub c: f64,
    /// Cooling effectiveness multiplier on AC kW.
    pub eta: f64,
    /// Comfort limit in °C.
    pub comfort_c: f64,
    /// Room temperature at 16:00 in °C.
    pub start_c: f64,
}

impl Default for ThermalParams {
    fn default() -> Self {
        ThermalParams {
            r: 1.6,
            c: 9.0,
            eta: 3.2,
            comfort_c: 25.0,
            start_c: 24.0,
        }
    }
}

/// A fully specified, reproducible simulation input.
///
/// Both runs for a scenario use these identical workloads, initial conditions, and
/// environmental inputs, so any peak reduction comes from scheduling, not from less work.
#[derive(Debug, Clone, PartialEq)]
pub struct Scenario {
    pub name: String,
    pub power_limit_kw: f64,
    pub devices: Vec<DeviceSpec>,
    /// Uncontrollable base load in kW, one value per minute (length `WINDOW_MINUTES`).
    pub base_load: Vec<f64>,
    /// Outdoor temperature in °C, one value per minute (length `WINDOW_MINUTES`).
    pub outdoor_c: Vec<f64>,
    pub thermal: ThermalParams,
    pub note: String,
}

/// Insertion-ordered map keyed by device id.
///
/// Python dicts preserve insertion order and the JSON contract follows it, so a small
/// `Vec`-backed map is used instead of a `HashMap` (whose iteration order is random).
#[derive(Debug, Clone, PartialEq)]
pub struct DeviceMap<T> {
    entries: Vec<(String, T)>,
}

impl<T> Default for DeviceMap<T> {
    fn default() -> Self {
        DeviceMap {
            entries: Vec::new(),
        }
    }
}

impl<T> DeviceMap<T> {
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert or replace the value for `id`, keeping first-insertion order.
    pub fn insert(&mut self, id: impl Into<String>, value: T) {
        let id = id.into();
        match self.entries.iter_mut().find(|(k, _)| *k == id) {
            Some(entry) => entry.1 = value,
            None => self.entries.push((id, value)),
        }
    }

    pub fn get(&self, id: &str) -> Option<&T> {
        self.entries.iter().find(|(k, _)| k == id).map(|(_, v)| v)
    }

    pub fn iter(&self) -> impl Iterator<Item = (&str, &T)> {
        self.entries.iter().map(|(k, v)| (k.as_str(), v))
    }

    pub fn values(&self) -> impl Iterator<Item = &T> {
        self.entries.iter().map(|(_, v)| v)
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// One plain-language decision-log line, emitted only on a state change.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecisionEntry {
    pub minute: u32,
    pub device: String,
    pub message: String,
}

/// Outcome of a single run (baseline or coordinated).
#[derive(Debug, Clone, PartialEq)]
pub struct RunResult {
    pub label: String,
    pub minutes: Vec<u32>,
    pub total_kw: Vec<f64>,
    pub per_device_kw: DeviceMap<Vec<f64>>,
    pub room_c: Vec<f64>,
    pub power_limit_kw: f64,
    pub peak_kw: f64,
    pub total_kwh: f64,
    pub per_device_kwh: DeviceMap<f64>,
    /// Only devices with an energy target appear here.
    pub tasks_met: DeviceMap<bool>,
    pub unmet_kwh: DeviceMap<f64>,
    pub minutes_over_limit: u32,
    pub temp_violation_min: u32,
    pub decision_log: Vec<DecisionEntry>,
}

impl RunResult {
    pub fn all_tasks_met(&self) -> bool {
        self.tasks_met.values().all(|met| *met)
    }
}

/// Baseline vs coordinated comparison for one scenario.
#[derive(Debug, Clone, PartialEq)]
pub struct CompareResult {
    pub scenario_name: String,
    pub power_limit_kw: f64,
    pub baseline: RunResult,
    pub coordinated: RunResult,
    pub comfort_c: f64,
}

impl CompareResult {
    /// Percentage by which coordination lowered the peak versus the baseline.
    pub fn peak_reduction_pct(&self) -> f64 {
        if self.baseline.peak_kw <= 0.0 {
            return 0.0;
        }
        100.0 * (self.baseline.peak_kw - self.coordinated.peak_kw) / self.baseline.peak_kw
    }
}
