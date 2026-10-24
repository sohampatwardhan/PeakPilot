//! Named, reproducible scenarios (pure standard library; all telemetry SIMULATED).
//!
//! Port of `peakpilot/scenarios.py`. Each scenario is described by [`ScenarioParams`] and
//! built deterministically by [`build`], so the CLI can override individual knobs (power
//! limit, EV / water-heater energy and deadlines) while keeping the rest of a scenario.

use crate::model::{DeviceKind, DeviceSpec, Scenario, ThermalParams, WINDOW_MINUTES};
use crate::solar::{PVArray, Solar};

/// EV deadline: 07:00, as minutes from 16:00.
pub const EV_DEADLINE: u32 = 15 * 60;
/// Water-heater deadline: 06:30, as minutes from 16:00.
pub const WH_DEADLINE: u32 = 14 * 60 + 30;

/// Knobs that fully determine a scenario.
#[derive(Debug, Clone, PartialEq)]
pub struct ScenarioParams {
    pub name: String,
    pub power_limit_kw: f64,
    pub ev_kwh: f64,
    pub ev_deadline_min: u32,
    pub wh_kwh: f64,
    pub wh_deadline_min: u32,
    /// Early-evening outdoor peak in °C (drives AC demand).
    pub peak_outdoor_c: f64,
    pub ev_offline: Option<(u32, u32)>,
    pub note: String,
    /// Add the SIMULATED rooftop PV array (clear-sky irradiance, default `PVArray`).
    pub solar: bool,
}

impl Default for ScenarioParams {
    /// Same defaults as Python `custom_scenario()`.
    fn default() -> Self {
        ScenarioParams {
            name: "Custom".to_string(),
            power_limit_kw: 14.0,
            ev_kwh: 30.0,
            ev_deadline_min: EV_DEADLINE,
            wh_kwh: 9.0,
            wh_deadline_min: WH_DEADLINE,
            peak_outdoor_c: 31.0,
            ev_offline: None,
            note: String::new(),
            solar: false,
        }
    }
}

/// A scenario the CLI can select by slug.
#[derive(Debug, Clone, Copy)]
pub struct NamedScenario {
    /// Command-line identifier, e.g. `hot_evening`.
    pub slug: &'static str,
    /// Label used by the Python dashboard's scenario picker.
    pub display_name: &'static str,
    pub params: fn() -> ScenarioParams,
}

/// Round to 4 decimals exactly like Python's `round(x, 4)`.
///
/// Python rounds using the correctly rounded decimal expansion of the binary value;
/// Rust's fixed-precision formatting does the same, so format-then-parse matches it
/// (unlike `(x * 1e4).round() / 1e4`, which can differ in the last digit).
fn round4(x: f64) -> f64 {
    format!("{x:.4}")
        .parse()
        .expect("formatted f64 always parses")
}

/// Hour of day for a step, as a float from 16.0 to 32.0 (matches the Python expression).
fn hour_of(m: usize) -> f64 {
    (16 * 60 + m) as f64 / 60.0
}

/// Uncontrollable base load in kW: an evening bump near 19:00 plus a small overnight one.
pub fn base_load_profile() -> Vec<f64> {
    (0..WINDOW_MINUTES)
        .map(|m| {
            let hour = hour_of(m);
            let d_eve = hour - 19.0;
            let d_night = hour - 28.0;
            let evening = 2.2 + 2.0 * (-(d_eve * d_eve) / 6.0).exp();
            let overnight = 0.6 * (-(d_night * d_night) / 20.0).exp();
            round4(evening + overnight)
        })
        .collect()
}

/// Outdoor temperature in °C: a cosine from a ~17:30 peak to a ~05:00 low.
pub fn outdoor_profile(peak_c: f64, low_c: f64) -> Vec<f64> {
    (0..WINDOW_MINUTES)
        .map(|m| {
            let hour = hour_of(m);
            // Same operation order as Python: (hour - 17.5) / 24.0 * 2 * pi.
            let frac = (((hour - 17.5) / 24.0 * 2.0 * std::f64::consts::PI).cos() + 1.0) / 2.0;
            round4(low_c + (peak_c - low_c) * frac)
        })
        .collect()
}

/// Illustrative clear-sky plane-of-array irradiance in W/m² (Boston summer, 05:15–20:20).
///
/// SIMULATED: not measured weather data, never derived from MassGIS installed capacity.
/// Same expression as the Python `clear_sky_irradiance()` defaults.
pub fn clear_sky_irradiance() -> Vec<f64> {
    let (peak_w_m2, sunrise_h, sunset_h) = (950.0_f64, 5.25_f64, 20.33_f64);
    (0..WINDOW_MINUTES)
        .map(|m| {
            let hour = hour_of(m) % 24.0;
            let frac = (hour - sunrise_h) / (sunset_h - sunrise_h);
            let g = if 0.0 < frac && frac < 1.0 {
                peak_w_m2 * (std::f64::consts::PI * frac).sin().powf(1.3)
            } else {
                0.0
            };
            round4(g)
        })
        .collect()
}

fn devices(p: &ScenarioParams) -> Vec<DeviceSpec> {
    vec![
        DeviceSpec {
            id: "ev-1".to_string(),
            kind: DeviceKind::Ev,
            max_kw: 7.2,
            min_run_min: 0,
            target_kwh: Some(p.ev_kwh),
            deadline_min: Some(p.ev_deadline_min),
            offline_window: p.ev_offline,
            commands: vec!["set_power", "pause", "resume"],
        },
        DeviceSpec {
            id: "wh-1".to_string(),
            kind: DeviceKind::WaterHeater,
            max_kw: 4.5,
            min_run_min: 15,
            target_kwh: Some(p.wh_kwh),
            deadline_min: Some(p.wh_deadline_min),
            offline_window: None,
            commands: vec!["on", "off"],
        },
        DeviceSpec {
            id: "ac-1".to_string(),
            kind: DeviceKind::AirConditioner,
            max_kw: 3.5,
            min_run_min: 10,
            target_kwh: None,
            deadline_min: None,
            offline_window: None,
            commands: vec!["on", "off"],
        },
    ]
}

/// Build a fully specified scenario from its parameters.
pub fn build(p: &ScenarioParams) -> Scenario {
    Scenario {
        name: p.name.clone(),
        power_limit_kw: p.power_limit_kw,
        devices: devices(p),
        base_load: base_load_profile(),
        outdoor_c: outdoor_profile(p.peak_outdoor_c, 19.0),
        thermal: ThermalParams::default(),
        note: p.note.clone(),
        solar: p.solar.then(|| Solar {
            irradiance_w_m2: clear_sky_irradiance(),
            array: PVArray::default(),
        }),
    }
}

/// Hot evening, 14 kW limit — the headline demo. Feasible; load shifts into the night.
pub fn hot_evening_params() -> ScenarioParams {
    ScenarioParams {
        name: "Hot evening (14 kW limit)".to_string(),
        power_limit_kw: 14.0,
        note: "Warm evening. Coordination shifts the EV and water heater into the night \
               and keeps the room under the comfort limit, all under 14 kW."
            .to_string(),
        ..ScenarioParams::default()
    }
}

/// Tighter 11 kW limit — still feasible, larger peak reduction.
pub fn tight_limit_params() -> ScenarioParams {
    ScenarioParams {
        name: "Tight limit (11 kW)".to_string(),
        power_limit_kw: 11.0,
        note: "A tighter 11 kW cap. Still feasible, so the limit holds with zero minutes over."
            .to_string(),
        ..ScenarioParams::default()
    }
}

/// EV charger offline 18:00–18:45 — exercises stale/offline handling.
pub fn ev_offline_params() -> ScenarioParams {
    ScenarioParams {
        name: "EV charger offline 18:00–18:45".to_string(),
        power_limit_kw: 14.0,
        ev_offline: Some((2 * 60, 2 * 60 + 45)),
        note: "The EV charger is uncommandable for 45 minutes. The controller reserves its \
               last power and defers other loads until it reconnects."
            .to_string(),
        ..ScenarioParams::default()
    }
}

/// 8 kW cap with a large, early (23:00) EV deadline on a hot evening — honestly infeasible.
pub fn infeasible_params() -> ScenarioParams {
    ScenarioParams {
        name: "Infeasible (8 kW, early EV deadline)".to_string(),
        power_limit_kw: 8.0,
        peak_outdoor_c: 34.0,
        ev_kwh: 40.0,
        ev_deadline_min: 7 * 60,
        note: "A hard case: a large EV charge is due early (23:00) under a tight 8 kW cap on \
               a hot evening. It cannot all fit. The controller runs the EV at full power as its \
               slack reaches zero and reports the minutes over the limit honestly."
            .to_string(),
        ..ScenarioParams::default()
    }
}

/// The tight 11 kW case plus a SIMULATED ~6 kW rooftop PV array with MPPT.
pub fn sunny_evening_params() -> ScenarioParams {
    ScenarioParams {
        name: "Sunny evening + rooftop PV (11 kW)".to_string(),
        power_limit_kw: 11.0,
        solar: true,
        note: "The tight 11 kW case with a SIMULATED ~6 kW rooftop PV array. Its inverter \
               tracks the maximum power point (perturb and observe). PV offsets demand until \
               sunset and again after sunrise, so the limit applies to net grid import. \
               Irradiance is an illustrative clear-sky curve, not measured data."
            .to_string(),
        ..ScenarioParams::default()
    }
}

pub fn hot_evening() -> Scenario {
    build(&hot_evening_params())
}

pub fn tight_limit() -> Scenario {
    build(&tight_limit_params())
}

pub fn ev_offline() -> Scenario {
    build(&ev_offline_params())
}

pub fn infeasible() -> Scenario {
    build(&infeasible_params())
}

pub fn sunny_evening() -> Scenario {
    build(&sunny_evening_params())
}

/// All named scenarios, in the same order as the Python dashboard registry.
pub fn all() -> [NamedScenario; 5] {
    [
        NamedScenario {
            slug: "hot_evening",
            display_name: "Hot evening (14 kW)",
            params: hot_evening_params,
        },
        NamedScenario {
            slug: "tight_limit",
            display_name: "Tight limit (11 kW)",
            params: tight_limit_params,
        },
        NamedScenario {
            slug: "ev_offline",
            display_name: "EV offline 18:00–18:45",
            params: ev_offline_params,
        },
        NamedScenario {
            slug: "infeasible",
            display_name: "Infeasible (8 kW, early EV deadline)",
            params: infeasible_params,
        },
        NamedScenario {
            slug: "sunny_evening",
            display_name: "Sunny evening + rooftop PV (11 kW)",
            params: sunny_evening_params,
        },
    ]
}

/// Parameters for the scenario with this slug, if it exists.
pub fn params_for(slug: &str) -> Option<ScenarioParams> {
    all().iter().find(|s| s.slug == slug).map(|s| (s.params)())
}
