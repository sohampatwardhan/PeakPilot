"""On-site PV with MPPT (issue #33): physics bounds, determinism and net-load scheduling."""

from __future__ import annotations

import dataclasses
import math

import pytest

from peakpilot import engine, optimal, scenarios
from peakpilot.engine import WINDOW_MINUTES, PVArray, Solar


@pytest.fixture(scope="module")
def sunny():
    s = scenarios.sunny_evening()
    return s, engine.compare(s)


def test_pv_is_zero_without_sun(sunny):
    s, cmp = sunny
    for g, kw in zip(s.solar.irradiance_w_m2, cmp.solar.pv_kw):
        if g <= 0:
            assert kw == 0.0
    # Night really happens inside the window (20:20 -> 05:15).
    assert any(g == 0 for g in s.solar.irradiance_w_m2)


def test_mppt_never_beats_the_true_mpp_or_the_inverter(sunny):
    s, cmp = sunny
    cap = s.solar.array.inverter_kw
    for pv, mpp in zip(cmp.solar.pv_kw, cmp.solar.mpp_kw):
        assert 0.0 <= pv <= mpp + 1e-9
        assert mpp <= cap + 1e-9


def test_mppt_tracks_close_to_the_maximum_power_point(sunny):
    _, cmp = sunny
    assert cmp.solar.tracking_efficiency >= 0.98
    assert cmp.solar.pv_kwh > 0


def test_true_mpp_beats_every_other_voltage():
    isc, voc, a = engine._pv_curve(800.0, 40.0, PVArray())
    best = engine._true_mpp_w(isc, voc, a)
    for i in range(1, 400):
        assert engine._pv_power_w(voc * i / 400, isc, voc, a) <= best + 1e-6


def test_inverter_clips_at_its_rating():
    small = PVArray(inverter_kw=2.0)
    s = dataclasses.replace(
        scenarios.sunny_evening(), solar=Solar(scenarios.clear_sky_irradiance(), small)
    )
    sol = engine.simulate_solar(s)
    assert max(sol.pv_kw) == pytest.approx(2.0)


def test_pv_is_deterministic():
    a = engine.compare(scenarios.sunny_evening()).to_json_dict()
    b = engine.compare(scenarios.sunny_evening()).to_json_dict()
    assert a == b


def test_both_runs_net_the_same_pv(sunny):
    s, cmp = sunny
    pv = cmp.solar.pv_kw
    for run in (cmp.baseline, cmp.coordinated):
        for m in range(WINDOW_MINUTES):
            drawn = sum(series[m] for series in run.per_device_kw.values())
            assert math.isclose(run.total_kw[m], s.base_load[m] - pv[m] + drawn, abs_tol=1e-9)


def test_sunny_scenario_is_feasible_and_honest(sunny):
    _, cmp = sunny
    co = cmp.coordinated
    assert co.all_tasks_met()
    assert co.minutes_over_limit == 0
    assert co.temp_violation_min == 0
    # Same deadline work as the no-solar tight case.
    assert cmp.baseline.tasks_met == co.tasks_met


def test_pv_lowers_the_uncoordinated_peak():
    with_pv = engine.compare(scenarios.sunny_evening()).baseline.peak_kw
    without = engine.compare(scenarios.tight_limit()).baseline.peak_kw
    assert with_pv < without


def test_no_solar_output_is_unchanged():
    out = engine.compare(scenarios.tight_limit()).to_json_dict()
    assert "solar" not in out
    assert engine.pv_kw_series(scenarios.tight_limit()) == (0.0,) * WINDOW_MINUTES


def test_solar_json_is_reported(sunny):
    _, cmp = sunny
    sol = cmp.to_json_dict()["solar"]
    assert len(sol["pv_kw"]) == WINDOW_MINUTES
    assert sol["tracking_efficiency"] == cmp.solar.tracking_efficiency


def test_lp_bound_uses_net_load():
    with_pv = optimal.solve(scenarios.sunny_evening()).peak_kw
    without = optimal.solve(scenarios.tight_limit()).peak_kw
    assert with_pv <= without + 1e-6
