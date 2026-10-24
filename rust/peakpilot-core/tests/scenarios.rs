//! Example-based tests on the named scenarios, mirroring `tests/test_engine.py` and `tests/test_solar.py`.

use peakpilot_core::{engine, json, scenarios, WINDOW_MINUTES};

#[test]
fn hot_evening_holds_the_limit_and_meets_every_deadline() {
    let c = engine::compare(&scenarios::hot_evening());
    assert_eq!(c.coordinated.minutes_over_limit, 0);
    assert!(c.coordinated.peak_kw <= c.power_limit_kw + 1e-6);
    assert!(c.coordinated.all_tasks_met());
    assert!(c.peak_reduction_pct() > 0.0);
}

#[test]
fn tight_limit_still_holds() {
    let c = engine::compare(&scenarios::tight_limit());
    assert_eq!(c.coordinated.minutes_over_limit, 0);
    assert!(c.coordinated.all_tasks_met());
}

#[test]
fn infeasible_scenario_reports_a_violation() {
    let r = engine::compare(&scenarios::infeasible()).coordinated;
    assert!(
        r.minutes_over_limit > 0 || r.temp_violation_min > 0,
        "an infeasible scenario must surface a power or comfort violation"
    );
}

#[test]
fn offline_ev_is_disclosed_and_recovers() {
    let r = engine::compare(&scenarios::ev_offline()).coordinated;
    let log: Vec<&str> = r.decision_log.iter().map(|d| d.message.as_str()).collect();
    assert!(log.iter().any(|m| m.contains("OFFLINE")));
    assert!(log.iter().any(|m| m.contains("reconnected")));
    assert!(*r.tasks_met.get("ev-1").unwrap());
}

#[test]
fn every_named_scenario_resolves_by_slug() {
    for s in scenarios::all() {
        let params = scenarios::params_for(s.slug).expect("slug resolves");
        assert_eq!(params, (s.params)());
    }
    assert!(scenarios::params_for("no_such_scenario").is_none());
}

#[test]
fn sunny_evening_nets_pv_and_holds_the_limit() {
    let s = scenarios::sunny_evening();
    let r = engine::compare(&s);
    let solar = r.solar.as_ref().expect("sunny evening has solar");
    let cap = s.solar.as_ref().unwrap().array.inverter_kw;
    for (pv, mpp) in solar.pv_kw.iter().zip(&solar.mpp_kw) {
        assert!(*pv >= 0.0 && *pv <= mpp + 1e-9 && *mpp <= cap + 1e-9);
    }
    assert!(solar.tracking_efficiency >= 0.98);
    for run in [&r.baseline, &r.coordinated] {
        for m in 0..WINDOW_MINUTES {
            let drawn: f64 = run.per_device_kw.values().map(|v| v[m]).sum();
            let expected = s.base_load[m] - solar.pv_kw[m] + drawn;
            assert!((run.total_kw[m] - expected).abs() < 1e-9);
        }
    }
    assert!(r.coordinated.all_tasks_met());
    assert_eq!(r.coordinated.minutes_over_limit, 0);
    assert!(r.baseline.peak_kw < engine::compare(&scenarios::tight_limit()).baseline.peak_kw);
}

#[test]
fn scenarios_without_solar_emit_no_solar_key() {
    let r = engine::compare(&scenarios::tight_limit());
    assert!(r.solar.is_none());
    let out = json::to_json_string(&r, false).unwrap();
    assert!(!out.contains("\"solar\""));
    let sunny = json::to_json_string(&engine::compare(&scenarios::sunny_evening()), false).unwrap();
    assert!(sunny.contains("\"tracking_efficiency\""));
}
