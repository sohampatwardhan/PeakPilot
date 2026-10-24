//! Simulation engine: uncoordinated baseline vs least-slack-first coordination.
//!
//! A line-for-line port of `run_baseline`, `run_coordinated`, and `compare` from
//! `peakpilot/engine.py`, written so the Rust and Python engines produce the same numbers.
//! Two details keep the floating-point results identical:
//!
//! * Arithmetic happens in the same order as the Python source (accumulating `committed`,
//!   the thermal step, `power / 60.0` energy increments).
//! * Wherever Python calls the built-in `sum()` on floats, [`py_sum`] reproduces CPython's
//!   compensated summation (CPython >= 3.12) instead of naive left-to-right addition.
//!
//! The control path uses only the standard library. Nothing here touches real hardware.

use crate::model::{
    CompareResult, DecisionEntry, DeviceKind, DeviceMap, DeviceState, RunResult, Scenario,
    ThermalParams, WINDOW_MINUTES,
};
use crate::solar::{simulate_solar, SolarResult};

/// Sum floats exactly as CPython >= 3.12's built-in `sum()` does.
///
/// CPython uses Neumaier's improved Kahan–Babuška compensation for float sums, which can
/// differ from naive summation in the last bits. Matching it keeps total kWh and the
/// baseline's per-minute totals bit-identical to the Python reference.
pub fn py_sum<I: IntoIterator<Item = f64>>(values: I) -> f64 {
    let mut sum = 0.0_f64;
    let mut compensation = 0.0_f64;
    for x in values {
        let t = sum + x;
        if sum.abs() >= x.abs() {
            compensation += (sum - t) + x;
        } else {
            compensation += (x - t) + sum;
        }
        sum = t;
    }
    // CPython only applies a nonzero, finite compensation, so an overflowed sum stays
    // infinite instead of turning into NaN.
    if compensation != 0.0 && compensation.is_finite() {
        sum += compensation;
    }
    sum
}

/// PV output for `scenario`, or `None` when it has no on-site solar.
pub fn scenario_solar(scenario: &Scenario) -> Option<SolarResult> {
    scenario
        .solar
        .as_ref()
        .map(|s| simulate_solar(s, &scenario.outdoor_c))
}

/// PV AC output in kW for every minute (all zeros when the scenario has no solar).
pub fn pv_kw_series(scenario: &Scenario) -> Vec<f64> {
    match scenario_solar(scenario) {
        Some(s) => s.pv_kw,
        None => vec![0.0; WINDOW_MINUTES],
    }
}

/// Python's two-argument `min(a, b)`: returns `a` unless `b < a`.
fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}

/// Advance the room temperature one minute (illustrative first-order RC model).
fn step_room_temp(room_c: f64, outdoor_c: f64, cooling_kw: f64, p: &ThermalParams) -> f64 {
    let dt = 1.0 / 60.0; // one minute in hours
    let heat_gain = (outdoor_c - room_c) / p.r;
    let net = heat_gain - cooling_kw * p.eta;
    room_c + (net / p.c) * dt * 60.0
}

/// Whole minutes of full-power running needed to deliver `remaining_kwh`.
fn minutes_needed(remaining_kwh: f64, max_kw: f64) -> i64 {
    if remaining_kwh <= 0.0 || max_kw <= 0.0 {
        return 0;
    }
    (remaining_kwh / max_kw * 60.0).ceil() as i64
}

/// Spare minutes for an energy task: time to deadline minus full-power minutes needed.
fn slack_of(s: &DeviceState, now: u32) -> i64 {
    let deadline = s
        .spec
        .deadline_min
        .expect("energy tasks always have a deadline");
    (deadline as i64 - now as i64) - minutes_needed(s.remaining_kwh(), s.spec.max_kw)
}

fn new_states(scenario: &Scenario) -> Vec<DeviceState> {
    scenario
        .devices
        .iter()
        .cloned()
        .map(DeviceState::new)
        .collect()
}

fn log(entries: &mut Vec<DecisionEntry>, minute: u32, device: &str, message: impl Into<String>) {
    entries.push(DecisionEntry {
        minute,
        device: device.to_string(),
        message: message.into(),
    });
}

/// An energy task's control state for one minute, mirroring Python's `_task_state`.
/// The coordinated run logs a decision only when this differs from the last minute's.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum TaskState {
    Done,
    Offline,
    Off,
    OverLimit,
    Throttled,
    Full,
}

/// Which pass-2 branch set a task's power this minute. Read only by the decision log.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Cause {
    Deadline,
    Paused,
    LockStart,
    WaitNow,
    WaitRun,
    Share,
}

/// Classify a task from its final power this minute (Python `_task_state`).
fn task_state(s: &DeviceState, breached: bool) -> TaskState {
    if s.remaining_kwh() <= 0.0 {
        TaskState::Done
    } else if !s.online {
        TaskState::Offline
    } else if s.power_kw <= 0.0 {
        TaskState::Off
    } else if breached {
        TaskState::OverLimit
    } else if s.power_kw < py_min(s.spec.max_kw, s.remaining_kwh() * 60.0) - 1e-9 {
        TaskState::Throttled
    } else {
        TaskState::Full
    }
}

/// Plain-language log line for a task moving from `prev` to `new` (Python `_task_message`).
fn task_message(s: &DeviceState, prev: TaskState, new: TaskState, cause: Option<Cause>) -> String {
    let text = match new {
        TaskState::Done => "task complete — stopping",
        TaskState::OverLimit => "deadline forces full power — exceeding limit (SIMULATED)",
        TaskState::Off => match cause {
            Some(Cause::WaitRun) => {
                return format!(
                    "heating OFF — limit too tight to guarantee a full {}-min run",
                    s.spec.min_run_min
                )
            }
            Some(Cause::WaitNow) => "heating OFF — not enough headroom for full power",
            _ => "paused to hold building under power limit",
        },
        TaskState::Throttled => match prev {
            TaskState::Full | TaskState::OverLimit => "throttled to fit power limit",
            _ => "resumed, throttled to fit power limit",
        },
        // Offline is announced by the OFFLINE line itself and is never classified as a
        // change from an online state here; the arm exists only for exhaustiveness.
        TaskState::Offline => "offline",
        TaskState::Full => match prev {
            TaskState::OverLimit => "full power now fits under the limit",
            TaskState::Throttled => "back to full power — headroom available",
            _ if s.spec.kind == DeviceKind::WaterHeater => match cause {
                Some(Cause::LockStart) => {
                    return format!("heating ON (min run {} min)", s.spec.min_run_min)
                }
                Some(Cause::Deadline) => "heating ON — deadline requires full power",
                _ => "heating ON",
            },
            _ => "resumed within available headroom",
        },
    };
    text.to_string()
}

/// Per-run series collected minute by minute.
struct Series {
    minutes: Vec<u32>,
    total_kw: Vec<f64>,
    per_device_kw: Vec<Vec<f64>>,
    room_c: Vec<f64>,
}

impl Series {
    fn new(devices: usize) -> Self {
        Series {
            minutes: Vec::with_capacity(WINDOW_MINUTES),
            total_kw: Vec::with_capacity(WINDOW_MINUTES),
            per_device_kw: vec![Vec::with_capacity(WINDOW_MINUTES); devices],
            room_c: Vec::with_capacity(WINDOW_MINUTES),
        }
    }
}

/// Compute run metrics, mirroring Python's `_finalize`.
fn finalize(
    label: &str,
    scenario: &Scenario,
    series: Series,
    states: &[DeviceState],
    decision_log: Vec<DecisionEntry>,
) -> RunResult {
    // Python's `max()` keeps the first maximum; `> ` reproduces that.
    let peak_kw = series
        .total_kw
        .iter()
        .copied()
        .reduce(|best, v| if v > best { v } else { best })
        .unwrap_or(0.0);
    let total_kwh = py_sum(series.total_kw.iter().copied()) / 60.0;

    let mut per_device_kw = DeviceMap::new();
    let mut per_device_kwh = DeviceMap::new();
    let mut tasks_met = DeviceMap::new();
    let mut unmet_kwh = DeviceMap::new();
    for (state, kw) in states.iter().zip(series.per_device_kw) {
        if let Some(target) = state.spec.target_kwh {
            // A deadline is met only by energy drawn before it; later energy still counts
            // in per_device_kwh but does not satisfy the task.
            let deadline = state
                .spec
                .deadline_min
                .expect("energy tasks always have a deadline") as usize;
            let by_deadline = kw[..deadline.min(kw.len())]
                .iter()
                .fold(0.0, |acc, p| acc + p / 60.0);
            let x = target - by_deadline;
            let unmet = if x > 0.0 { x } else { 0.0 }; // Python max(0.0, x)
            unmet_kwh.insert(state.spec.id.clone(), unmet);
            tasks_met.insert(state.spec.id.clone(), unmet <= 1e-6);
        }
        per_device_kw.insert(state.spec.id.clone(), kw);
        per_device_kwh.insert(state.spec.id.clone(), state.delivered_kwh);
    }

    let limit = scenario.power_limit_kw + 1e-9;
    let comfort = scenario.thermal.comfort_c + 1e-9;
    let minutes_over_limit = series.total_kw.iter().filter(|&&v| v > limit).count() as u32;
    let temp_violation_min = series.room_c.iter().filter(|&&t| t > comfort).count() as u32;

    RunResult {
        label: label.to_string(),
        minutes: series.minutes,
        total_kw: series.total_kw,
        per_device_kw,
        room_c: series.room_c,
        power_limit_kw: scenario.power_limit_kw,
        peak_kw,
        total_kwh,
        per_device_kwh,
        tasks_met,
        unmet_kwh,
        minutes_over_limit,
        temp_violation_min,
        decision_log,
    }
}

/// Uncoordinated run: every device pulls full power while it has work.
///
/// The AC is a reactive thermostat at the comfort limit; energy tasks run flat out until
/// met; the power limit is ignored. Same workload and inputs as the coordinated run.
pub fn run_baseline(scenario: &Scenario) -> RunResult {
    let mut states = new_states(scenario);
    let mut series = Series::new(states.len());
    let mut decisions = Vec::new();
    let mut room_c = scenario.thermal.start_c;
    let pv = pv_kw_series(scenario);

    for (step, &pv_now) in pv.iter().enumerate() {
        let m = step as u32;
        let mut cooling_kw = 0.0;

        for (i, s) in states.iter_mut().enumerate() {
            let online = s.spec.is_online_at(m);
            let prev_online = s.online;
            s.online = online;
            if online {
                s.last_update_min = m;
            }
            if online != prev_online {
                let msg = if online {
                    "came online"
                } else {
                    "went OFFLINE (SIMULATED)"
                };
                log(&mut decisions, m, &s.spec.id, msg);
            }

            let power = if s.spec.kind == DeviceKind::AirConditioner {
                let want_on = room_c >= scenario.thermal.comfort_c || s.run_remaining_min > 0;
                let p = if want_on && online {
                    s.spec.max_kw
                } else {
                    0.0
                };
                if p > 0.0 && s.power_kw == 0.0 {
                    s.run_remaining_min = s.spec.min_run_min;
                }
                cooling_kw = p;
                p
            } else if online && s.remaining_kwh() > 0.0 {
                py_min(s.spec.max_kw, s.remaining_kwh() * 60.0)
            } else {
                0.0
            };

            s.power_kw = power;
            s.delivered_kwh += power / 60.0;
            if s.run_remaining_min > 0 {
                s.run_remaining_min -= 1;
            }
            series.per_device_kw[i].push(power);
        }

        let step_total =
            py_sum(states.iter().map(|s| s.power_kw)) + scenario.base_load[step] - pv_now;
        series.minutes.push(m);
        series.total_kw.push(step_total);
        series.room_c.push(room_c);
        room_c = step_room_temp(
            room_c,
            scenario.outdoor_c[step],
            cooling_kw,
            &scenario.thermal,
        );
    }

    finalize("Uncoordinated", scenario, series, &states, decisions)
}

/// Coordinated run: deterministic, two-pass least-slack-first scheduling under the limit.
///
/// Each minute, pass 1 commits loads that cannot be throttled this minute (base load,
/// offline devices assumed to hold their last power, AC priority near the comfort limit,
/// and a water heater inside its minimum run). Pass 2 hands the remaining headroom to the
/// energy tasks in ascending slack order. A task with no slack left runs at full power even
/// past the limit, and the breach is logged. The log records state changes only.
pub fn run_coordinated(scenario: &Scenario) -> RunResult {
    let mut states = new_states(scenario);
    let mut series = Series::new(states.len());
    let mut decisions = Vec::new();
    let thermal = &scenario.thermal;
    let mut room_c = thermal.start_c;
    let pv = pv_kw_series(scenario);
    let ac_idx = states
        .iter()
        .position(|s| s.spec.kind == DeviceKind::AirConditioner);
    let wh_idx = states
        .iter()
        .position(|s| s.spec.kind == DeviceKind::WaterHeater);
    let ac_reserve_kw = ac_idx.map(|a| states[a].spec.max_kw).unwrap_or(0.0);
    let limit = scenario.power_limit_kw;
    // Last logged control state per energy task (None for the AC).
    let mut last_state: Vec<Option<TaskState>> = states
        .iter()
        .map(|s| {
            s.spec.kind.is_energy_task().then(|| {
                if s.remaining_kwh() <= 0.0 {
                    TaskState::Done
                } else {
                    TaskState::Off
                }
            })
        })
        .collect();

    for step in 0..WINDOW_MINUTES {
        let m = step as u32;
        let mut committed = scenario.base_load[step] - pv[step]; // net of on-site PV
        let mut cooling_kw = 0.0;

        // Refresh online state and disclose offline transitions.
        for (i, s) in states.iter_mut().enumerate() {
            let online = s.spec.is_online_at(m);
            let prev_online = s.online;
            s.online = online;
            if online != prev_online {
                let msg = if online {
                    "reconnected; resuming control".to_string()
                } else {
                    // The OFFLINE line is this task's state-change entry.
                    if let Some(st) = last_state[i].as_mut() {
                        if *st != TaskState::Done {
                            *st = TaskState::Offline;
                        }
                    }
                    format!(
                        "OFFLINE — holding last power {:.1} kW, reserving headroom (SIMULATED)",
                        s.power_kw
                    )
                };
                log(&mut decisions, m, &s.spec.id, msg);
            }
            if online {
                s.last_update_min = m;
            }
        }

        // ---- Pass 1: commit forced loads ----
        // (a) Offline devices are assumed to hold their last commanded power.
        for s in states.iter().filter(|s| !s.online) {
            committed += s.power_kw;
        }

        // (b) AC priority: cool when the room nears the comfort limit, honoring min run.
        if let Some(a) = ac_idx {
            let ac = &mut states[a];
            if ac.online {
                // 0.8 °C of pre-emptive margin keeps feasible scenarios from overshooting.
                let near_limit = room_c >= thermal.comfort_c - 0.8;
                if near_limit || ac.run_remaining_min > 0 {
                    if ac.power_kw == 0.0 {
                        ac.run_remaining_min = ac.spec.min_run_min;
                        log(
                            &mut decisions,
                            m,
                            &ac.spec.id,
                            "cooling ON — room near comfort limit (priority)",
                        );
                    }
                    ac.power_kw = ac.spec.max_kw;
                } else {
                    if ac.power_kw > 0.0 && ac.run_remaining_min == 0 {
                        log(
                            &mut decisions,
                            m,
                            &ac.spec.id,
                            "cooling OFF — room within comfort band",
                        );
                    }
                    ac.power_kw = 0.0;
                }
                if ac.run_remaining_min > 0 {
                    ac.run_remaining_min -= 1;
                }
                cooling_kw = ac.power_kw;
                committed += ac.power_kw;
            }
        }

        // (c) A water heater inside its minimum run must keep going at full power.
        let mut wh_locked = false;
        if let Some(w) = wh_idx {
            let wh = &mut states[w];
            if wh.online && wh.run_remaining_min > 0 && wh.remaining_kwh() > 0.0 {
                wh.power_kw = py_min(wh.spec.max_kw, wh.remaining_kwh() * 60.0);
                committed += wh.power_kw;
                wh.run_remaining_min -= 1;
                wh_locked = true;
            }
        }

        // ---- Pass 2: distribute remaining headroom, least slack first ----
        let mut startable: Vec<usize> = (0..states.len())
            .filter(|&i| {
                let s = &states[i];
                s.online
                    && s.spec.kind.is_energy_task()
                    && s.remaining_kwh() > 0.0
                    && !(Some(i) == wh_idx && wh_locked)
            })
            .collect();
        // Stable sort on (slack, id), the same key as the Python implementation.
        startable.sort_by(|&a, &b| {
            (slack_of(&states[a], m), &states[a].spec.id)
                .cmp(&(slack_of(&states[b], m), &states[b].spec.id))
        });

        // Which pass-2 branch set each task's power, and which tasks breached the limit.
        // Read only by the decision log below; never by the scheduler.
        let mut cause: Vec<Option<Cause>> = vec![None; states.len()];
        let mut breached = vec![false; states.len()];

        for i in startable {
            let s = &mut states[i];
            let slack = slack_of(s, m);
            let headroom = limit - committed;
            let full = py_min(s.spec.max_kw, s.remaining_kwh() * 60.0);

            let power = if slack <= 0 {
                // Out of slack: full power even if that breaches the limit.
                cause[i] = Some(Cause::Deadline);
                breached[i] = full > headroom + 1e-9;
                full
            } else if headroom <= 1e-9 {
                cause[i] = Some(Cause::Paused);
                0.0
            } else if s.spec.kind == DeviceKind::WaterHeater {
                // On/off device: start only if the limit holds for the whole minimum run,
                // using the worst base load in that window plus a full AC reservation.
                let end = (step + s.spec.min_run_min as usize).min(WINDOW_MINUTES);
                let worst_base = (step..end.max(step + 1))
                    .map(|t| scenario.base_load[t] - pv[t])
                    .reduce(|best, v| if v > best { v } else { best })
                    .unwrap_or(scenario.base_load[step] - pv[step]);
                let forecast_floor = worst_base + ac_reserve_kw + s.spec.max_kw;
                let fits_now = headroom >= s.spec.max_kw - 1e-9;
                let fits_run = forecast_floor <= limit + 1e-9;
                if fits_now && fits_run {
                    s.run_remaining_min = s.spec.min_run_min.saturating_sub(1);
                    cause[i] = Some(Cause::LockStart);
                    py_min(s.spec.max_kw, s.remaining_kwh() * 60.0)
                } else {
                    // Too tight to guarantee the whole run; wait for a quieter window.
                    cause[i] = Some(if fits_run {
                        Cause::WaitNow
                    } else {
                        Cause::WaitRun
                    });
                    0.0
                }
            } else {
                // EV: continuously throttleable, absorbs the remaining headroom.
                cause[i] = Some(Cause::Share);
                py_min(full, headroom)
            };

            s.power_kw = power;
            committed += power;
        }

        // ---- Commit energy and record series for every device, in device order ----
        for (i, s) in states.iter_mut().enumerate() {
            let is_task = s.spec.kind.is_energy_task();
            if s.remaining_kwh() <= 0.0 && is_task && s.power_kw > 0.0 {
                s.power_kw = 0.0;
            } else if is_task && !s.online {
                // An offline device stops on its own at its target, so it never draws
                // more than it still owes. The controller still reserved its last power.
                s.power_kw = py_min(s.power_kw, s.remaining_kwh() * 60.0);
            }
            if let Some(prev) = last_state[i] {
                // Log only when the task's control state differs from last minute's.
                let new = task_state(s, breached[i]);
                if new != prev {
                    let msg = task_message(s, prev, new, cause[i]);
                    log(&mut decisions, m, &s.spec.id, msg);
                    last_state[i] = Some(new);
                }
            }
            s.delivered_kwh += s.power_kw / 60.0;
            series.per_device_kw[i].push(s.power_kw);
        }

        series.minutes.push(m);
        // Report what the building actually drew, not the controller's reservation.
        series
            .total_kw
            .push(py_sum(states.iter().map(|s| s.power_kw)) + scenario.base_load[step] - pv[step]);
        series.room_c.push(room_c);
        room_c = step_room_temp(room_c, scenario.outdoor_c[step], cooling_kw, thermal);
    }

    finalize(
        "PeakPilot coordinated",
        scenario,
        series,
        &states,
        decisions,
    )
}

/// Run baseline and coordinated simulations for `scenario` and compare them.
pub fn compare(scenario: &Scenario) -> CompareResult {
    CompareResult {
        scenario_name: scenario.name.clone(),
        power_limit_kw: scenario.power_limit_kw,
        baseline: run_baseline(scenario),
        coordinated: run_coordinated(scenario),
        comfort_c: scenario.thermal.comfort_c,
        solar: scenario_solar(scenario),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn py_sum_matches_cpython_compensated_sum() {
        // CPython >= 3.12: sum([0.1] * 10) == 1.0; naive summation gives 0.9999999999999999.
        assert_eq!(py_sum(std::iter::repeat_n(0.1, 10)), 1.0);
        let naive: f64 = std::iter::repeat_n(0.1, 10).sum();
        assert_ne!(naive, 1.0);
    }

    #[test]
    fn py_sum_of_nothing_is_zero() {
        assert_eq!(py_sum(std::iter::empty()), 0.0);
    }

    #[test]
    fn minutes_needed_rounds_up() {
        assert_eq!(minutes_needed(7.2, 7.2), 60);
        assert_eq!(minutes_needed(0.01, 7.2), 1);
        assert_eq!(minutes_needed(0.0, 7.2), 0);
    }
}
