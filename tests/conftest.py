"""Shared pytest fixtures for the PeakPilot suite.

Everything here is standard library + the ``peakpilot`` package, so the engine,
scenario and MassGIS tests run with only ``pip install pytest``. Dashboard tests
(``tests/test_app.py``) bring their own Streamlit import and skip without it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from peakpilot import scenarios
from peakpilot.engine import Scenario

REPO_ROOT = Path(__file__).resolve().parent.parent

# Display names of every named scenario, in registry order. Used to parametrize.
SCENARIO_NAMES = list(scenarios.scenarios().keys())


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def scenario_registry() -> dict[str, Callable[[], Scenario]]:
    """The dashboard's scenario registry: display name -> zero-arg builder."""
    return scenarios.scenarios()


@pytest.fixture(params=SCENARIO_NAMES)
def named_scenario(request, scenario_registry) -> tuple[str, Scenario]:
    """``(display name, freshly built Scenario)`` for every named scenario."""
    name = request.param
    return name, scenario_registry[name]()
