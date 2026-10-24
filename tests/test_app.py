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

from peakpilot import massgis, scenarios  # noqa: E402

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
    assert len(at.metric) == 5


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
