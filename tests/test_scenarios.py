"""Scenario builder tests (spec: .kiro/specs/test-framework, R3).

Named scenarios are the inputs every demo and engine test relies on. These check
that each one is well-formed, deterministic, and built from the same base load.
"""

from __future__ import annotations

import pytest

from peakpilot import engine, scenarios
from peakpilot.engine import WINDOW_MINUTES, DeviceKind

EXPECTED_DEVICES = {
    "ev-1": DeviceKind.EV,
    "wh-1": DeviceKind.WATER_HEATER,
    "ac-1": DeviceKind.AIR_CONDITIONER,
}


def test_registry_lists_four_named_scenarios(scenario_registry):
    assert len(scenario_registry) == 4
    assert all(callable(builder) for builder in scenario_registry.values())


def test_registry_returns_a_copy():
    """Mutating the returned dict must not change the dashboard's registry."""
    reg = scenarios.scenarios()
    reg.clear()
    assert len(scenarios.scenarios()) == 4


def test_profiles_span_the_window(named_scenario):
    _, s = named_scenario
    assert len(s.base_load) == WINDOW_MINUTES
    assert len(s.outdoor_c) == WINDOW_MINUTES
    assert all(kw > 0 for kw in s.base_load)


def test_three_expected_devices(named_scenario):
    _, s = named_scenario
    assert {d.id: d.kind for d in s.devices} == EXPECTED_DEVICES


def test_deadlines_and_targets_are_inside_the_window(named_scenario):
    _, s = named_scenario
    for d in s.devices:
        if d.kind is DeviceKind.AIR_CONDITIONER:
            continue  # thermal-driven, no energy task
        assert d.target_kwh > 0, d.id
        assert 0 < d.deadline_min <= WINDOW_MINUTES, d.id
    assert s.power_limit_kw > 0


def test_offline_window_is_inside_the_window(named_scenario):
    _, s = named_scenario
    for d in s.devices:
        if d.offline_window is not None:
            start, end = d.offline_window
            assert 0 <= start < end <= WINDOW_MINUTES, d.id


def test_every_scenario_has_a_note(named_scenario):
    """The dashboard shows ``note`` as the scenario explanation."""
    _, s = named_scenario
    assert s.note.strip()


def test_builders_are_deterministic(scenario_registry):
    for name, builder in scenario_registry.items():
        assert builder() == builder(), name


def test_all_scenarios_share_the_base_load(scenario_registry):
    loads = {name: builder().base_load for name, builder in scenario_registry.items()}
    first = next(iter(loads.values()))
    assert all(load == first for load in loads.values())


def test_outdoor_peak_follows_parameter():
    hot = scenarios.custom_scenario(peak_outdoor_c=34.0)
    mild = scenarios.custom_scenario(peak_outdoor_c=25.0)
    assert max(hot.outdoor_c) > max(mild.outdoor_c)
    assert max(mild.outdoor_c) <= 25.0 + 1e-9


def test_custom_scenario_overrides_reach_the_devices():
    s = scenarios.custom_scenario(
        power_limit_kw=12.5,
        ev_kwh=22.0,
        ev_deadline_min=600,
        wh_kwh=6.0,
        wh_deadline_min=500,
        ev_offline=(30, 90),
    )
    by_id = {d.id: d for d in s.devices}
    assert s.power_limit_kw == 12.5
    assert by_id["ev-1"].target_kwh == 22.0
    assert by_id["ev-1"].deadline_min == 600
    assert by_id["ev-1"].offline_window == (30, 90)
    assert by_id["wh-1"].target_kwh == 6.0
    assert by_id["wh-1"].deadline_min == 500


def test_ev_offline_scenario_marks_the_charger_offline():
    s = scenarios.ev_offline()
    ev = next(d for d in s.devices if d.id == "ev-1")
    assert ev.offline_window == (120, 165)  # 18:00-18:45
    assert not ev.is_online_at(120)
    assert ev.is_online_at(165)


@pytest.mark.parametrize("builder", [scenarios.hot_evening, scenarios.tight_limit])
def test_feasible_scenarios_are_feasible(builder):
    """Scenarios described as feasible must actually hold their limit."""
    run = engine.compare(builder()).coordinated
    assert run.minutes_over_limit == 0
    assert run.all_tasks_met()
