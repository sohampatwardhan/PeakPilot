"""Headless dashboard smoke test (spec: .kiro/specs/test-framework, R5).

Runs ``app.py`` through Streamlit's ``AppTest`` for every named scenario and checks
that it renders without exceptions and keeps the honesty labels: SIMULATED device
data, MassGIS source + snapshot date, and the capacity-is-not-generation caveat.
Skipped when the dashboard dependencies (requirements.txt) are not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("pandas")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from pathlib import Path  # noqa: E402

from peakpilot import engine, massgis, optimal, scenarios  # noqa: E402

pytestmark = pytest.mark.dashboard

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SCENARIO_NAMES = list(scenarios.scenarios().keys())
# The first run imports pandas and Plotly; AppTest's 3 s default is too short.
TIMEOUT_S = 30


def _run(scenario_name: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT_S)
    at.run()
    if scenario_name is not None:
        at.sidebar.selectbox[0].set_value(scenario_name).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _all_text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    parts += [s.value for s in at.subheader]
    return "\n".join(parts)


@pytest.mark.parametrize("scenario_name", SCENARIO_NAMES)
def test_every_scenario_renders(scenario_name):
    at = _run(scenario_name)
    assert at.sidebar.selectbox[0].value == scenario_name
    assert at.title[0].value == "PeakPilot"
    # 5 headline metrics + 3 in the "How close to optimal?" panel (every named
    # scenario has a solvable benchmark).
    assert len(at.metric) == 8
    assert "How close to optimal? (SIMULATED)" in [s.value for s in at.subheader]
    assert any(m.label == "Lower bound on achievable peak (kW)" for m in at.metric)


def test_simulated_labels_present():
    text = _all_text(_run())
    assert "SIMULATED" in text
    assert "Device status (SIMULATED)" in text


def test_massgis_source_and_snapshot_date_shown():
    text = _all_text(_run())
    assert massgis.SOURCE in text
    assert massgis.PORTAL_SNAPSHOT_DATE in text
    assert "not** generation" in text


def test_feasible_headline_reports_zero_minutes_over():
    at = _run()
    over = next(m for m in at.metric if m.label == "Min over limit")
    assert over.value == "0"
    assert not at.warning


def test_infeasible_scenario_shows_honest_warning():
    at = _run("Infeasible (8 kW, early EV deadline)")
    assert at.warning
    assert "Honest infeasibility" in at.warning[0].value


def test_deadline_sliders_use_clock_labels():
    at = _run()
    labels = {s.label: s for s in at.sidebar.select_slider}
    for name in ("EV deadline", "Water-heater deadline"):
        slider = labels[name]
        assert slider.options[0] == "17:00"
        assert slider.options[-1] == "08:00"
        assert "07:00" in slider.options
        assert "06:30" in slider.options  # half-hour steps: the water heater's default


def test_deadline_slider_values_are_minutes_from_1600():
    at = _run()
    ev = next(s for s in at.sidebar.select_slider if s.label == "EV deadline")
    ev.set_value(240).run()  # 240 minutes after 16:00 == 20:00
    assert not at.exception
    ev = next(s for s in at.sidebar.select_slider if s.label == "EV deadline")
    assert ev.value == 240
    assert ev.format_func(ev.value) == "20:00"
    wh = next(s for s in at.sidebar.select_slider if s.label == "Water-heater deadline")
    assert wh.value == 870 and wh.format_func(870) == "06:30"


@pytest.mark.parametrize("scenario_name", SCENARIO_NAMES)
def test_default_sliders_reproduce_the_named_scenario(scenario_name):
    # Issue #19: with untouched sliders the dashboard must run exactly the named scenario,
    # including its outdoor temperature (Infeasible is a 34 °C evening) and the water
    # heater's 06:30 deadline.
    at = _run(scenario_name)
    expected = engine.compare(scenarios.scenarios()[scenario_name]())
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Coordinated peak"] == f"{expected.coordinated.peak_kw:.1f} kW"
    assert metrics["Baseline peak"] == f"{expected.baseline.peak_kw:.1f} kW"
    assert metrics["Min over limit"] == f"{expected.coordinated.minutes_over_limit}"
    bound = optimal.solve(scenarios.scenarios()[scenario_name]()).peak_kw
    assert metrics["Lower bound on achievable peak (kW)"] == f"{bound:.2f}"


def test_peak_cards_show_units():
    at = _run()
    peaks = {m.label: m.value for m in at.metric}
    assert peaks["Coordinated peak"].endswith(" kW")
    assert peaks["Baseline peak"].endswith(" kW")
    assert peaks["Energy delivered"].endswith(" kWh")


def test_energy_delta_is_neutral_when_tasks_match():
    at = _run()  # Hot evening: every task met, so only AC runtime can differ
    energy = next(m for m in at.metric if m.label == "Energy delivered")
    assert "AC runtime" in energy.delta or energy.delta == "same as baseline"


def test_ac_cycling_hidden_by_default_and_toggle_restores_it():
    at = _run()
    log = at.dataframe[0].value
    assert not log["message"].str.startswith(("cooling ON", "cooling OFF")).any()
    hidden_rows = len(log)

    at.toggle[0].set_value(True).run()
    assert not at.exception
    full = at.dataframe[0].value
    assert full["message"].str.startswith(("cooling ON", "cooling OFF")).any()
    assert len(full) > hidden_rows
