//! Property-based tests (proptest) for the PeakPilot engine.
//!
//! Each property is checked against hundreds of generated scenarios: random power limits,
//! EV and water-heater energy targets and deadlines, evening temperatures, and an optional
//! EV offline window. They encode the honesty rules in `.kiro/steering/product.md`:
//! energy is accounted for exactly, "deadline met" means the energy arrived before the
//! deadline, and the reported building total is what the devices actually drew.

use peakpilot_core::scenarios::{self, ScenarioParams};
use peakpilot_core::{engine, RunResult, Scenario, WINDOW_MINUTES};
use proptest::prelude::*;
use proptest::test_runner::TestCaseError;

/// Generated scenarios span the dashboard's slider ranges, plus hotter evenings and an
/// optional EV outage of up to two hours anywhere in the window.
fn arb_params() -> impl Strategy<Value = ScenarioParams> {
    (
        8.0f64..20.0,
        5.0f64..60.0,
        60u32..=960,
        2.0f64..20.0,
        60u32..=960,
        25.0f64..36.0,
        proptest::option::of((0u32..900, 1u32..=120)),
    )
        .prop_map(
            |(limit, ev_kwh, ev_deadline, wh_kwh, wh_deadline, peak_c, outage)| ScenarioParams {
                name: "generated".to_string(),
                power_limit_kw: limit,
                ev_kwh,
                ev_deadline_min: ev_deadline,
                wh_kwh,
                wh_deadline_min: wh_deadline,
                peak_outdoor_c: peak_c,
                ev_offline: outage
                    .map(|(start, len)| (start, (start + len).min(WINDOW_MINUTES as u32))),
                note: String::new(),
            },
        )
}

/// Energy (kWh) drawn in minutes `[0, minutes)`, accumulated in step order like the engine.
fn energy_before(series: &[f64], minutes: usize) -> f64 {
    series[..minutes.min(series.len())]
        .iter()
        .fold(0.0, |acc, p| acc + p / 60.0)
}

/// Physical and reporting invariants that every run must satisfy.
fn check_run(s: &Scenario, r: &RunResult) -> Result<(), TestCaseError> {
    let n = WINDOW_MINUTES;
    prop_assert_eq!(r.total_kw.len(), n);
    prop_assert_eq!(r.room_c.len(), n);

    for spec in &s.devices {
        let kw = r.per_device_kw.get(&spec.id).expect("a series for every device");
        prop_assert_eq!(kw.len(), n);
        for (m, &p) in kw.iter().enumerate() {
            prop_assert!(
                (0.0..=spec.max_kw + 1e-9).contains(&p),
                "{} ({}): {} kW at minute {} is outside 0..={} kW",
                spec.id, r.label, p, m, spec.max_kw
            );
        }

        // Energy conservation: delivered kWh is the integral of the power series.
        let delivered = *r.per_device_kwh.get(&spec.id).unwrap();
        let integral = energy_before(kw, n);
        prop_assert!(
            (delivered - integral).abs() <= 1e-9 * (1.0 + delivered),
            "{} ({}): delivered {} kWh but its power series integrates to {} kWh",
            spec.id, r.label, delivered, integral
        );

        if let Some(target) = spec.target_kwh {
            prop_assert!(
                delivered <= target + 1e-6,
                "{} ({}): delivered {} kWh, more than the {} kWh asked for",
                spec.id, r.label, delivered, target
            );
            // Honest deadlines: only energy drawn before the deadline counts.
            let deadline = spec.deadline_min.expect("energy tasks have a deadline") as usize;
            let shortfall = (target - energy_before(kw, deadline)).max(0.0);
            let met = *r.tasks_met.get(&spec.id).unwrap();
            prop_assert_eq!(
                met,
                shortfall <= 1e-6,
                "{} ({}): tasks_met={} but {:.3} kWh was still owed at the deadline (minute {})",
                spec.id, r.label, met, shortfall, deadline
            );
            let unmet = *r.unmet_kwh.get(&spec.id).unwrap();
            prop_assert!(
                (unmet - shortfall).abs() <= 1e-9,
                "{} ({}): unmet_kwh={} but the shortfall at the deadline is {}",
                spec.id, r.label, unmet, shortfall
            );
        }
    }

    // The reported building total is base load plus what the devices actually drew.
    for m in 0..n {
        let drawn: f64 = s
            .devices
            .iter()
            .map(|d| r.per_device_kw.get(&d.id).unwrap()[m])
            .sum();
        let expected = s.base_load[m] + drawn;
        prop_assert!(
            (r.total_kw[m] - expected).abs() <= 1e-6,
            "{}: total {} kW at minute {} but base + devices = {} kW",
            r.label, r.total_kw[m], m, expected
        );
    }

    // Headline metrics agree with the series they summarize.
    let peak = r.total_kw.iter().copied().fold(f64::MIN, f64::max);
    prop_assert_eq!(r.peak_kw, peak);
    let over = r
        .total_kw
        .iter()
        .filter(|&&v| v > s.power_limit_kw + 1e-9)
        .count() as u32;
    prop_assert_eq!(r.minutes_over_limit, over);
    Ok(())
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]

    /// Power bounds, energy conservation, honest deadlines, and consistent totals.
    #[test]
    fn every_run_is_physically_consistent_and_honest(p in arb_params()) {
        let s = scenarios::build(&p);
        let c = engine::compare(&s);
        check_run(&s, &c.baseline)?;
        check_run(&s, &c.coordinated)?;
    }

    /// Identical inputs give bit-identical results.
    #[test]
    fn identical_inputs_give_identical_outputs(p in arb_params()) {
        let s = scenarios::build(&p);
        prop_assert_eq!(engine::compare(&s), engine::compare(&s));
    }

    /// When both runs meet every deadline, they delivered the same energy to each task, so
    /// any peak reduction came from timing, not from doing less work.
    #[test]
    fn same_work_when_both_runs_meet_every_deadline(p in arb_params()) {
        let s = scenarios::build(&p);
        let c = engine::compare(&s);
        if c.baseline.all_tasks_met() && c.coordinated.all_tasks_met() {
            for (id, _) in c.baseline.tasks_met.iter() {
                let b = *c.baseline.per_device_kwh.get(id).unwrap();
                let k = *c.coordinated.per_device_kwh.get(id).unwrap();
                prop_assert!((b - k).abs() <= 2e-6, "{}: baseline {} kWh vs coordinated {} kWh", id, b, k);
            }
        }
    }
}
