"""Learned analysis models (peakpilot.learn; spec: .kiro/specs/ml-models, R2, R3, R6).

Property-based tests (Hypothesis) check thermal-model recovery over the whole
parameter range; the rest pin the study results the spec was written against.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from peakpilot import engine, learn, optimal, scenarios
from peakpilot.engine import ThermalParams

STUDY_RESULTS = Path(".kiro/specs/ml-models/studies/results")  # relative to the repo root


def _true_ab(p: ThermalParams) -> tuple[float, float]:
    return 1.0 / (p.r * p.c), p.eta / p.c


def _synthetic(a: float, b: float, minutes: int, period: int, on_min: int) -> tuple[list, list, list]:
    """Noise-free telemetry from the RC model with a square-wave AC (3.5 kW)."""
    outdoor = list(scenarios.custom_scenario().outdoor_c[:minutes])
    ac = [3.5 if (t % period) < on_min else 0.0 for t in range(minutes)]
    room = [24.0]
    for t in range(minutes - 1):
        room.append(room[t] + a * (outdoor[t] - room[t]) - b * ac[t])
    return room, outdoor, ac


# --- Thermal calibration: properties ------------------------------------------


@settings(max_examples=60, deadline=None, derandomize=True)
@given(
    a=st.floats(0.02, 0.2),
    b=st.floats(0.1, 1.0),
    minutes=st.integers(120, 480),
    period=st.integers(10, 60),
    duty=st.floats(0.2, 0.8),
)
def test_fit_recovers_any_parameters_from_clean_data(a, b, minutes, period, duty):
    # R6.1: noise-free data with at least 30 AC-on minutes recovers a and b to 1e-6.
    on_min = max(1, int(period * duty))
    room, outdoor, ac = _synthetic(a, b, minutes, period, on_min)
    assume(sum(1 for x in ac[:-1] if x > 0) >= 30)
    fit = learn.fit_thermal(room, outdoor, ac)
    assert fit.a == pytest.approx(a, rel=1e-6)
    assert fit.b == pytest.approx(b, rel=1e-6)
    assert fit.rmse_c < 1e-6


@settings(max_examples=30, deadline=None, derandomize=True)
@given(a=st.floats(0.02, 0.2), b=st.floats(0.1, 1.0))
def test_fitted_params_map_back_to_a_and_b(a, b):
    room, outdoor, ac = _synthetic(a, b, 240, 30, 12)
    prior = ThermalParams()
    fit = learn.fit_thermal(room, outdoor, ac, prior=prior)
    # Only a and b are identifiable; C is kept from the prior.
    assert fit.params.c == prior.c
    assert 1.0 / (fit.params.r * fit.params.c) == pytest.approx(fit.a, rel=1e-12)
    assert fit.params.eta / fit.params.c == pytest.approx(fit.b, rel=1e-12)
    assert fit.params.comfort_c == prior.comfort_c and fit.params.start_c == prior.start_c


# --- Thermal calibration: study results and validation ------------------------


def test_fit_matches_study_s1_at_0_2_c_noise_240_min():
    # Acceptance criterion 3, on the exact S1 noise draw (seed 20261024, fourth noise level).
    scenario = scenarios.hot_evening()
    run = engine.run_coordinated(scenario)
    rng = np.random.default_rng(learn.SEED)
    noise = {s: rng.normal(0, s, len(run.room_c)) if s else None for s in (0.0, 0.05, 0.1, 0.2)}
    room = (np.asarray(run.room_c) + noise[0.2])[:240].tolist()
    fit = learn.fit_thermal(room, list(scenario.outdoor_c[:240]), run.per_device_kw["ac-1"][:240])
    a, b = _true_ab(scenario.thermal)
    assert abs(fit.a / a - 1) < 0.01 and abs(fit.b / b - 1) < 0.01


def test_fit_matches_study_csv(repo_root):
    # learn.fit_thermal is the study's S1 output-error method: same numbers on the same data.
    results = repo_root / STUDY_RESULTS
    rows = (results / "s1_telemetry.csv").read_text().splitlines()[1:]
    cols = list(zip(*(r.split(",") for r in rows)))
    fit = learn.fit_thermal([float(x) for x in cols[1]], [float(x) for x in cols[2]], [float(x) for x in cols[3]])
    study = json.loads((results / "s1_thermal_id.json").read_text())
    oe = next(r for r in study["rows"] if r["method"] == "OE" and r["noise_c"] == 0.1 and r["train_min"] == 960)
    assert fit.a == pytest.approx(oe["a"], rel=1e-6)
    assert fit.b == pytest.approx(oe["b"], rel=1e-6)


@pytest.mark.parametrize("builder", list(scenarios.scenarios().values()))
def test_simulated_telemetry_calibrates_every_scenario(builder):
    scenario = builder()
    fit = learn.fit_thermal(*learn.simulated_telemetry(scenario))
    a, b = _true_ab(scenario.thermal)
    assert abs(fit.a / a - 1) < 0.01 and abs(fit.b / b - 1) < 0.01
    assert "output-error" in fit.method


def test_simulated_telemetry_is_seeded():
    scenario = scenarios.hot_evening()
    assert learn.simulated_telemetry(scenario) == learn.simulated_telemetry(scenario)
    assert learn.simulated_telemetry(scenario, seed=1) != learn.simulated_telemetry(scenario, seed=2)
    clean_room = learn.simulated_telemetry(scenario, noise_c=0.0)[0]
    assert clean_room == engine.run_coordinated(scenario).room_c


def test_fit_is_deterministic():
    data = learn.simulated_telemetry(scenarios.hot_evening())
    assert learn.fit_thermal(*data) == learn.fit_thermal(*data)


@pytest.mark.parametrize(
    ("room", "outdoor", "ac", "match"),
    [
        ([24.0] * 100, [30.0] * 99, [1.0] * 100, "same length"),
        ([24.0] * 59, [30.0] * 59, [1.0] * 59, "at least 60"),
        ([24.0] * 100, [30.0] * 100, [0.0] * 100, "never runs"),
        ([math.nan] + [24.0] * 99, [30.0] * 100, [1.0] * 100, "non-finite"),
        ([24.0] * 100, [30.0] * 100, [-1.0] * 100, ">= 0"),
    ],
)
def test_fit_rejects_bad_telemetry(room, outdoor, ac, match):
    with pytest.raises(ValueError, match=match):
        learn.fit_thermal(room, outdoor, ac)


def test_simulated_telemetry_rejects_negative_noise():
    with pytest.raises(ValueError):
        learn.simulated_telemetry(scenarios.hot_evening(), noise_c=-0.1)


# --- Forecast cost ------------------------------------------------------------


def test_zero_error_is_the_perfect_foresight_bound():
    # R6.3: a perfect forecast plans and realizes the LP bound, with no comfort violations.
    scenario = scenarios.hot_evening()
    cost = learn.forecast_cost(scenario, learn.ForecastError())
    bound = optimal.solve(scenario).peak_kw
    assert cost.status == "optimal"
    assert cost.planned_peak_kw == pytest.approx(bound)
    assert cost.realized_peak_kw == pytest.approx(bound, abs=1e-6)
    assert cost.comfort_violation_min == 0


def test_reproduces_study_s2_part_a(repo_root):
    # Acceptance criterion 4: every S2 Part A row to +/-0.01 kW. The 0.5 kW noise row
    # used the study's second noise draw, so it is checked for direction only.
    rows = json.loads((repo_root / STUDY_RESULTS / "s2_forecast_value.json").read_text())
    rows = {c["case"]: c for c in rows["part_a"]["cases"]}
    errors = {
        "perfect": learn.ForecastError(),
        "base x0.9": learn.ForecastError(scale=0.9),
        "base x1.1": learn.ForecastError(scale=1.1),
        "base x1.2": learn.ForecastError(scale=1.2),
        "base 30 min early": learn.ForecastError(shift_min=-30),
        "base 60 min early": learn.ForecastError(shift_min=-60),
        "base 30 min late": learn.ForecastError(shift_min=30),
        "base 60 min late": learn.ForecastError(shift_min=60),
        "base noise 0.2 kW": learn.ForecastError(noise_kw=0.2),
        "outdoor -2 °C": learn.ForecastError(outdoor_bias_c=-2.0),
        "outdoor +2 °C": learn.ForecastError(outdoor_bias_c=2.0),
    }
    scenario = scenarios.hot_evening()
    for case, error in errors.items():
        cost = learn.forecast_cost(scenario, error)
        assert cost.realized_peak_kw == pytest.approx(rows[case]["realized_peak_kw"], abs=0.01), case
        assert cost.comfort_violation_min == rows[case]["comfort_violation_min"], case
    noisy = learn.forecast_cost(scenario, learn.ForecastError(noise_kw=0.5))
    assert noisy.realized_peak_kw > rows["base noise 0.2 kW"]["realized_peak_kw"]


def test_cool_bias_breaks_comfort():
    cost = learn.forecast_cost(scenarios.hot_evening(), learn.ForecastError(outdoor_bias_c=-2.0))
    assert cost.comfort_violation_min > 0


def test_forecast_cost_reports_infeasible_plan():
    cost = learn.forecast_cost(scenarios.custom_scenario(ev_kwh=60, ev_deadline_min=60), learn.ForecastError())
    assert cost == learn.ForecastCost("infeasible", None, None, None)


@pytest.mark.parametrize(
    "kwargs",
    [{"scale": 0.7}, {"scale": 1.3}, {"shift_min": 61}, {"noise_kw": -0.1}, {"noise_kw": 0.6}, {"outdoor_bias_c": 3.5}],
)
def test_forecast_error_validates_ranges(kwargs):
    with pytest.raises(ValueError):
        learn.ForecastError(**kwargs)


def test_forecast_cost_is_deterministic():
    scenario = scenarios.hot_evening()
    error = learn.ForecastError(noise_kw=0.3, shift_min=15)
    assert learn.forecast_cost(scenario, error) == learn.forecast_cost(scenario, error)
