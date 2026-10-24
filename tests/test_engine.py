"""Engine correctness tests — the properties PeakPilot must never violate.

Run with ``pytest -q``. These guard the honest-metrics claims in the product
steering: energy accounting, same-work-both-runs, determinism, feasible limits
holding, and honest infeasibility.
"""

from __future__ import annotations

import math

from peakpilot import engine, scenarios
from peakpilot.engine import WINDOW_MINUTES


def _sum_energy(per_device_kw: dict[str, list[float]], device: str) -> float:
    return sum(per_device_kw[device]) / 60.0


# --- P1: energy conservation ------------------------------------------------


def test_p1_energy_conservation():
    """Per-device delivered kWh == integral of its power series (both runs)."""
    result = engine.compare(scenarios.hot_evening())
    for run in (result.baseline, result.coordinated):
        for dev_id, delivered in run.per_device_kwh.items():
            series_kwh = _sum_energy(run.per_device_kw, dev_id)
            assert math.isclose(delivered, series_kwh, rel_tol=1e-6, abs_tol=1e-6), (
                f"{run.label} {dev_id}: delivered {delivered} vs series {series_kwh}"
            )


def test_series_length():
    """Every series spans the full window."""
    result = engine.compare(scenarios.hot_evening())
    for run in (result.baseline, result.coordinated):
        assert len(run.total_kw) == WINDOW_MINUTES
        assert len(run.room_c) == WINDOW_MINUTES
        for series in run.per_device_kw.values():
            assert len(series) == WINDOW_MINUTES


# --- P2: same work both runs ------------------------------------------------


def test_p2_same_work_when_feasible():
    """On a feasible scenario, coordinated delivers the same energy tasks as baseline."""
    result = engine.compare(scenarios.hot_evening())
    assert result.coordinated.all_tasks_met()
    assert result.baseline.all_tasks_met()
    # EV and water heater deliver their targets in both runs.
    for dev_id in ("ev-1", "wh-1"):
        assert math.isclose(
            result.baseline.per_device_kwh[dev_id],
            result.coordinated.per_device_kwh[dev_id],
            rel_tol=1e-3,
            abs_tol=0.05,
        ), dev_id


# --- P3: determinism --------------------------------------------------------


def test_p3_determinism():
    """compare() twice yields identical serialized output."""
    a = engine.compare(scenarios.hot_evening()).to_json_dict()
    b = engine.compare(scenarios.hot_evening()).to_json_dict()
    assert a == b


# --- P4: feasible limit holds -----------------------------------------------


def test_p4_feasible_limit_holds():
    """Coordinated run keeps a feasible scenario at or under the limit."""
    result = engine.compare(scenarios.hot_evening())
    assert result.coordinated.minutes_over_limit == 0
    assert result.coordinated.peak_kw <= result.power_limit_kw + 1e-6


def test_p4_peak_reduction_positive():
    """Coordination reduces the peak versus the uncoordinated baseline."""
    result = engine.compare(scenarios.hot_evening())
    assert result.coordinated.peak_kw < result.baseline.peak_kw
    assert result.peak_reduction_pct > 0


def test_tight_limit_holds():
    result = engine.compare(scenarios.tight_limit())
    assert result.coordinated.minutes_over_limit == 0
    assert result.coordinated.all_tasks_met()


# --- P5: honest infeasibility ----------------------------------------------


def test_p5_infeasible_is_reported():
    """An over-tight scenario surfaces a violation rather than hiding one.

    Infeasibility can show up as either minutes over the power limit or
    temperature-comfort violations. The point is that the controller reports it; a
    clean result with everything satisfied would mean the scenario wasn't actually
    infeasible.
    """
    result = engine.compare(scenarios.infeasible())
    r = result.coordinated
    violated = r.minutes_over_limit > 0 or r.temp_violation_min > 0
    assert violated, "infeasible scenario should report a power or comfort violation"


def test_infeasible_does_not_hide_by_dropping_work():
    """A lower peak must not come from silently abandoning required energy.

    Either the energy tasks are still delivered (and the limit/comfort breaks), or
    any shortfall is explicitly reported in unmet_kwh — never hidden.
    """
    result = engine.compare(scenarios.infeasible())
    r = result.coordinated
    for dev_id, unmet in r.unmet_kwh.items():
        if unmet > 1e-6:
            assert r.tasks_met[dev_id] is False  # shortfall is reported, not hidden
    # Energy work is attempted, not quietly skipped to fake a low peak.
    assert r.per_device_kwh["ev-1"] > 0


# --- Offline handling -------------------------------------------------------


def test_offline_device_logs_and_recovers():
    """EV offline window produces offline + reconnect log entries."""
    result = engine.compare(scenarios.ev_offline())
    messages = " ".join(d.message.lower() for d in result.coordinated.decision_log)
    assert "offline" in messages
    assert "reconnect" in messages or "resuming" in messages
    # EV still ultimately meets its target once back online.
    assert result.coordinated.tasks_met["ev-1"]


# --- Metrics sanity ---------------------------------------------------------


def test_metrics_present():
    result = engine.compare(scenarios.hot_evening())
    j = result.to_json_dict()
    for key in ("peak_kw", "total_kwh", "per_device_kwh", "tasks_met", "minutes_over_limit"):
        assert key in j["coordinated"]
    assert j["peak_reduction_pct"] >= 0


# --- Regressions found by the Rust property tests ---------------------------


def test_late_delivery_does_not_count_as_meeting_the_deadline():
    """60 kWh by 17:00 is impossible at 7.2 kW; finishing later must be reported as unmet."""
    s = scenarios.custom_scenario(ev_kwh=60.0, ev_deadline_min=60)
    for run in (engine.compare(s).baseline, engine.compare(s).coordinated):
        assert run.tasks_met["ev-1"] is False
        by_deadline = sum(run.per_device_kw["ev-1"][:60]) / 60.0
        assert math.isclose(run.unmet_kwh["ev-1"], 60.0 - by_deadline, abs_tol=1e-9)


def test_offline_device_never_draws_past_its_target():
    """A small EV charge finishing during an outage must stop at its target."""
    s = scenarios.custom_scenario(ev_kwh=5.0, ev_offline=(20, 140))
    run = engine.compare(s).coordinated
    assert run.per_device_kwh["ev-1"] <= 5.0 + 1e-6
    for m in range(WINDOW_MINUTES):
        drawn = sum(series[m] for series in run.per_device_kw.values())
        assert math.isclose(run.total_kw[m], s.base_load[m] + drawn, abs_tol=1e-9)


# --- Decision log: one entry per state change (R2.6, issue #25) -------------

# Named scenarios plus custom ones that reach rarer branches: an EV finishing during an
# outage, a water heater that cannot fit a full min run, and a heavily overloaded night.
_LOG_SCENARIOS = [build() for build in scenarios.SCENARIOS.values()] + [
    scenarios.custom_scenario(ev_kwh=5.0, ev_offline=(20, 140)),
    scenarios.custom_scenario(power_limit_kw=9.0, wh_deadline_min=600),
    scenarios.custom_scenario(power_limit_kw=6.0, ev_kwh=50.0, ev_deadline_min=300, peak_outdoor_c=35.0),
]


def _device_log(run, device: str) -> list[engine.DecisionEntry]:
    return [d for d in run.decision_log if d.device == device]


def test_log_has_no_consecutive_duplicate_messages():
    """No device logs the same message twice in a row: the log records changes only."""
    for s in _LOG_SCENARIOS:
        run = engine.run_coordinated(s)
        for device in run.per_device_kw:
            messages = [d.message for d in _device_log(run, device)]
            repeats = [a for a, b in zip(messages, messages[1:]) if a == b]
            assert not repeats, f"{s.name} {device}: repeated {repeats[:1]}"


def test_water_heater_on_and_off_transitions_are_logged():
    """Every off->on and on->off edge in the water-heater power series has a log entry."""
    for s in _LOG_SCENARIOS:
        run = engine.run_coordinated(s)
        series = run.per_device_kw["wh-1"]
        logged = {d.minute for d in _device_log(run, "wh-1")}
        edges = [m for m in range(1, WINDOW_MINUTES) if (series[m - 1] > 0) != (series[m] > 0)]
        if series[0] > 0:
            edges.insert(0, 0)
        assert edges, s.name
        missing = [engine.clock(m) for m in edges if m not in logged]
        assert not missing, f"{s.name}: unlogged water-heater transitions at {missing}"


def test_ev_return_from_throttled_to_full_is_logged():
    """An EV stepping up from a throttled rate to its full rate gets a log entry."""
    seen = 0
    for s in _LOG_SCENARIOS:
        run = engine.run_coordinated(s)
        ev = run.per_device_kw["ev-1"]
        max_kw = next(d.max_kw for d in s.devices if d.id == "ev-1")
        logged = {d.minute: d.message for d in _device_log(run, "ev-1")}
        for m in range(1, WINDOW_MINUTES):
            if 0 < ev[m - 1] < max_kw - 1e-9 and ev[m] >= max_kw - 1e-9:
                seen += 1
                assert m in logged, f"{s.name}: EV back to full at {engine.clock(m)} not logged"
                assert "throttled" not in logged[m]
    assert seen > 0  # the scenarios do exercise this transition


def test_deadline_breach_logged_once_per_episode():
    """A deadline-forced breach is logged once per contiguous over-limit episode."""
    breach = "deadline forces full power"
    for s in _LOG_SCENARIOS:
        run = engine.run_coordinated(s)
        over = [v > s.power_limit_kw + 1e-9 for v in run.total_kw]
        episode, current = [], -1
        for m in range(WINDOW_MINUTES):
            if over[m] and (m == 0 or not over[m - 1]):
                current += 1
            episode.append(current if over[m] else None)
        for device in run.per_device_kw:
            hits = [d.minute for d in _device_log(run, device) if d.message.startswith(breach)]
            assert all(episode[m] is not None for m in hits), f"{s.name} {device}: breach outside over-limit"
            per_episode = [episode[m] for m in hits]
            assert len(per_episode) == len(set(per_episode)), f"{s.name} {device}: breach re-logged"
    infeasible = engine.run_coordinated(scenarios.infeasible())
    hits = [d for d in infeasible.decision_log if d.message.startswith(breach)]
    assert len(hits) == 1 and hits[0].device == "ev-1"


def test_log_fix_left_scheduling_unchanged():
    """Coordinated metrics pinned to their values before the decision-log fix (#25)."""
    expected = {
        # name: (peak_kw, ev_kwh, wh_kwh, ac_kwh, minutes_over_limit, temp_violation_min)
        "Hot evening (14 kW)": (14.0, 30.0, 9.0, 12.25, 0, 0),
        "Tight limit (11 kW)": (11.0, 30.0, 9.0, 12.25, 0, 0),
        "EV offline 18:00–18:45": (14.2907, 30.0, 9.0, 12.25, 25, 0),
        "Infeasible (8 kW, early EV deadline)": (14.9102, 40.0, 9.0, 15.75, 291, 0),
    }
    for name, build in scenarios.SCENARIOS.items():
        run = engine.run_coordinated(build())
        kwh = run.per_device_kwh
        got = (
            round(run.peak_kw, 4),
            round(kwh["ev-1"], 4),
            round(kwh["wh-1"], 4),
            round(kwh["ac-1"], 4),
            run.minutes_over_limit,
            run.temp_violation_min,
        )
        assert got == expected[name], name
        assert run.all_tasks_met(), name
