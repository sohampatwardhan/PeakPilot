"""Correctness properties of the perfect-foresight LP benchmark (peakpilot.optimal)."""

from __future__ import annotations

import dataclasses
import time

import pytest

from peakpilot import engine, optimal, scenarios
from peakpilot.engine import DeviceKind

NAMED = list(scenarios.scenarios().items())
IDS = [name for name, _ in NAMED]


@pytest.fixture(scope="module", params=NAMED, ids=IDS)
def solved(request):
    """(scenario, coordinated run, benchmark) for each named scenario, solved once."""
    scenario = request.param[1]()
    coordinated = engine.run_coordinated(scenario)
    return scenario, coordinated, optimal.benchmark(scenario, coordinated)


def test_solves_optimally_within_two_seconds(solved):
    _, _, bench = solved
    assert bench.optimal.status == "optimal"
    assert bench.optimal.solve_time_s < 2.0


def test_bound_not_above_coordinated_peak(solved):
    _, coordinated, bench = solved
    # Every named scenario's coordinated run meets every deadline and the comfort
    # limit, so its schedule is a feasible LP point and the LP optimum cannot exceed it.
    assert bench.coordinated_comparable
    assert bench.optimal.peak_kw <= coordinated.peak_kw + 1e-6
    assert bench.gap_kw >= -1e-6


def test_energy_met_by_deadline(solved):
    scenario, _, bench = solved
    for d in scenario.devices:
        if d.kind is DeviceKind.AIR_CONDITIONER:
            continue
        series = bench.optimal.per_device_kw[d.id]
        assert sum(series[: d.deadline_min]) / 60.0 == pytest.approx(d.target_kwh, abs=1e-6)
        assert all(kw == 0.0 for kw in series[d.deadline_min :])


def test_power_limits_and_peak(solved):
    scenario, _, bench = solved
    for d in scenario.devices:
        assert all(-1e-9 <= kw <= d.max_kw + 1e-9 for kw in bench.optimal.per_device_kw[d.id])
    assert bench.optimal.peak_kw == pytest.approx(max(bench.optimal.total_kw), abs=1e-6)
    for t, total in enumerate(bench.optimal.total_kw):
        expected = scenario.base_load[t] + sum(s[t] for s in bench.optimal.per_device_kw.values())
        assert total == pytest.approx(expected, abs=1e-9)


def test_comfort_limit_and_thermal_model(solved):
    scenario, _, bench = solved
    room = bench.optimal.room_c
    assert len(room) == engine.WINDOW_MINUTES
    assert max(room) <= scenario.thermal.comfort_c + 1e-6
    # Replaying the LP's AC series through the engine's own thermal step reproduces
    # the LP room temperatures, so the LP uses exactly the engine's model.
    ac = next(d for d in scenario.devices if d.kind is DeviceKind.AIR_CONDITIONER)
    ac_kw = bench.optimal.per_device_kw[ac.id]
    replay = scenario.thermal.start_c
    for t in range(engine.WINDOW_MINUTES):
        assert room[t] == pytest.approx(replay, abs=1e-6)
        replay = engine._step_room_temp(replay, scenario.outdoor_c[t], ac_kw[t], scenario.thermal)


def test_reproducible(solved):
    scenario, coordinated, bench = solved
    again = optimal.benchmark(scenario, engine.run_coordinated(scenario))
    assert again.to_json_dict() == bench.to_json_dict()


def test_offline_ev_holds_last_power():
    scenario = scenarios.ev_offline()
    ev = next(d for d in scenario.devices if d.kind is DeviceKind.EV)
    start, end = ev.offline_window
    series = optimal.solve(scenario).per_device_kw[ev.id]
    assert all(series[t] == series[start - 1] for t in range(start, end))


def test_infeasible_lp_reports_no_number():
    # 60 kWh by 17:00 needs 60 kW for an hour; the EV charger tops out at 7.2 kW.
    scenario = scenarios.custom_scenario(ev_kwh=60, ev_deadline_min=60)
    bench = optimal.benchmark(scenario, engine.run_coordinated(scenario))
    assert bench.optimal.status == "infeasible"
    assert bench.optimal.peak_kw is None
    assert bench.gap_kw is None and bench.gap_pct is None and bench.limit_achievable is None


def test_infeasible_scenario_limit_cannot_be_met():
    scenario = scenarios.infeasible()
    bench = optimal.benchmark(scenario, engine.run_coordinated(scenario))
    assert bench.optimal.peak_kw > scenario.power_limit_kw
    assert bench.limit_achievable is False


def test_result_is_labeled_lower_bound():
    result = optimal.solve(scenarios.hot_evening())
    assert result.is_lower_bound
    assert result.relaxations == optimal.RELAXATIONS and result.relaxations


# --- Reactive floor (spec: .kiro/specs/ml-models, R1) -----------------------


@pytest.mark.parametrize(
    ("builder", "limit_kw", "monotone"),
    [
        (scenarios.hot_evening, 7.8, True),
        (scenarios.tight_limit, 7.8, True),
        # The engine holds the EV's last power through its outage, so only 14.9-15.4 kW
        # and >= 19.0 kW hold every constraint: feasibility is not monotone in the limit.
        (scenarios.ev_offline, 14.9, False),
        (scenarios.infeasible, 11.7, True),
    ],
)
def test_reactive_floor_on_named_scenarios(builder, limit_kw, monotone):
    floor = optimal.reactive_floor(builder())
    assert floor.limit_kw == limit_kw
    assert floor.monotone is monotone
    assert floor.peak_kw <= floor.limit_kw + 1e-9
    assert floor.grid_kw[0] == 5.0 and floor.grid_kw[2] == 0.1


def test_reactive_floor_limit_really_holds():
    scenario = scenarios.hot_evening()
    floor = optimal.reactive_floor(scenario)
    at_floor = engine.run_coordinated(dataclasses.replace(scenario, power_limit_kw=floor.limit_kw))
    below = engine.run_coordinated(dataclasses.replace(scenario, power_limit_kw=floor.limit_kw - 0.1))
    assert at_floor.minutes_over_limit == 0 and at_floor.all_tasks_met() and at_floor.temp_violation_min == 0
    assert below.minutes_over_limit > 0 or not below.all_tasks_met() or below.temp_violation_min > 0


def test_reactive_floor_none_when_no_limit_works():
    # Unreachable EV deadline: no limit lets the scheduler finish the work.
    floor = optimal.reactive_floor(scenarios.custom_scenario(ev_kwh=60, ev_deadline_min=60))
    assert floor.limit_kw is None and floor.peak_kw is None and floor.monotone is False


def test_reactive_floor_rejects_bad_step():
    with pytest.raises(ValueError):
        optimal.reactive_floor(scenarios.hot_evening(), step_kw=0)


def _coverage_active() -> bool:
    try:
        import coverage
    except ImportError:
        return False
    return coverage.Coverage.current() is not None


def test_reactive_floor_grid_is_bounded():
    # R1.5's cost driver: one engine run per grid point, at most ~151 for named scenarios.
    for builder in scenarios.scenarios().values():
        start, stop, step = optimal.reactive_floor(builder()).grid_kw
        assert round((stop - start) / step) + 1 <= 151


@pytest.mark.skipif(_coverage_active(), reason="branch tracing slows the engine ~3x; timing is checked without --cov")
def test_reactive_floor_is_fast():
    # R1.5: under 1 s for every named scenario (the dashboard caches it too).
    for builder in scenarios.scenarios().values():
        t0 = time.perf_counter()
        optimal.reactive_floor(builder())
        assert time.perf_counter() - t0 < 1.0


def test_benchmark_headroom_hot_evening():
    # Acceptance criterion 1: floor 7.8 kW, bound 6.03 kW, headroom 1.77 kW (about 23 %).
    scenario = scenarios.hot_evening()
    bench = optimal.benchmark(scenario, engine.run_coordinated(scenario))
    assert bench.floor.limit_kw == 7.8
    assert bench.optimal.peak_kw == pytest.approx(6.03, abs=0.005)
    assert bench.headroom_kw == pytest.approx(7.8 - bench.optimal.peak_kw)
    assert bench.headroom_pct == pytest.approx(22.7, abs=0.1)
    assert bench.to_json_dict()["floor"]["limit_kw"] == 7.8


def test_benchmark_headroom_none_without_floor():
    scenario = scenarios.custom_scenario(ev_kwh=60, ev_deadline_min=60)
    bench = optimal.benchmark(scenario, engine.run_coordinated(scenario))
    assert bench.floor.limit_kw is None
    assert bench.headroom_kw is None and bench.headroom_pct is None
