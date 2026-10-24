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
