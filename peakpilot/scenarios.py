"""Named, reproducible PeakPilot scenarios (all telemetry SIMULATED).

Each builder returns a fully specified :class:`~peakpilot.engine.Scenario`: a base
load profile, an outdoor-temperature profile, three device specs, and a power
limit. Profiles are generated deterministically (no randomness), so a scenario
always simulates identically. ``custom_scenario`` lets the dashboard override the
power limit and the EV / water-heater energy and deadlines from the UI.
"""

from __future__ import annotations

import math

from .engine import (
    WINDOW_MINUTES,
    DeviceKind,
    DeviceSpec,
    Scenario,
    ThermalParams,
)


def _base_load_profile() -> tuple[float, ...]:
    """Uncontrollable household base load in kW across the 16:00->08:00 window.

    A smooth evening peak (lights, cooking, electronics) that eases overnight.
    Deterministic — a fixed cosine bump centered on the early evening.
    """
    vals: list[float] = []
    for m in range(WINDOW_MINUTES):
        hour = (16 * 60 + m) / 60.0  # 16.0 .. 32.0
        # Evening peak around 19:00, trough around 04:00.
        evening = 2.2 + 2.0 * math.exp(-((hour - 19.0) ** 2) / 6.0)
        overnight = 0.6 * math.exp(-((hour - 28.0) ** 2) / 20.0)
        vals.append(round(evening + overnight, 4))
    return tuple(vals)


def _outdoor_profile(peak_c: float = 31.0, low_c: float = 19.0) -> tuple[float, ...]:
    """Outdoor temperature in °C across the window.

    Warm late-afternoon carryover that cools overnight. ``peak_c`` sets how hot the
    early evening is (drives AC demand); ``low_c`` the pre-dawn low.
    """
    vals: list[float] = []
    for m in range(WINDOW_MINUTES):
        hour = (16 * 60 + m) / 60.0
        # Cosine from an ~17:30 warmth peak to an ~05:00 low.
        frac = (math.cos((hour - 17.5) / 24.0 * 2 * math.pi) + 1) / 2
        vals.append(round(low_c + (peak_c - low_c) * frac, 4))
    return tuple(vals)


def _devices(
    ev_kwh: float,
    ev_deadline_min: int,
    wh_kwh: float,
    wh_deadline_min: int,
    ev_offline: tuple[int, int] | None = None,
) -> tuple[DeviceSpec, ...]:
    return (
        DeviceSpec(
            id="ev-1",
            kind=DeviceKind.EV,
            max_kw=7.2,
            min_run_min=0,  # continuously throttleable
            target_kwh=ev_kwh,
            deadline_min=ev_deadline_min,
            offline_window=ev_offline,
            commands=("set_power", "pause", "resume"),
        ),
        DeviceSpec(
            id="wh-1",
            kind=DeviceKind.WATER_HEATER,
            max_kw=4.5,
            min_run_min=15,
            target_kwh=wh_kwh,
            deadline_min=wh_deadline_min,
            commands=("on", "off"),
        ),
        DeviceSpec(
            id="ac-1",
            kind=DeviceKind.AIR_CONDITIONER,
            max_kw=3.5,
            min_run_min=10,
            commands=("on", "off"),
        ),
    )


# Deadlines are minutes from 16:00. 07:00 == 15h == 900 min; 06:30 == 870 min.
EV_DEADLINE = 15 * 60  # 07:00
WH_DEADLINE = 14 * 60 + 30  # 06:30


def custom_scenario(
    name: str = "Custom",
    power_limit_kw: float = 14.0,
    ev_kwh: float = 30.0,
    ev_deadline_min: int = EV_DEADLINE,
    wh_kwh: float = 9.0,
    wh_deadline_min: int = WH_DEADLINE,
    peak_outdoor_c: float = 31.0,
    ev_offline: tuple[int, int] | None = None,
    note: str = "",
) -> Scenario:
    """Build a scenario from dashboard-adjustable parameters (SIMULATED)."""
    return Scenario(
        name=name,
        power_limit_kw=power_limit_kw,
        devices=_devices(ev_kwh, ev_deadline_min, wh_kwh, wh_deadline_min, ev_offline),
        base_load=_base_load_profile(),
        outdoor_c=_outdoor_profile(peak_c=peak_outdoor_c),
        thermal=ThermalParams(),
        note=note,
    )


def hot_evening() -> Scenario:
    """Hot evening, 14 kW limit — the headline demo. Feasible; peak shifts to night."""
    return custom_scenario(
        name="Hot evening (14 kW limit)",
        power_limit_kw=14.0,
        note="Warm evening. Coordination shifts the EV and water heater into the night "
        "and keeps the room under the comfort limit, all under 14 kW.",
    )


def tight_limit() -> Scenario:
    """Tighter 11 kW limit — still feasible, larger peak reduction."""
    return custom_scenario(
        name="Tight limit (11 kW)",
        power_limit_kw=11.0,
        note="A tighter 11 kW cap. Still feasible, so the limit holds with zero minutes over.",
    )


def ev_offline() -> Scenario:
    """EV charger drops offline 18:00–18:45 — tests stale/offline handling."""
    start = 2 * 60  # 18:00
    end = 2 * 60 + 45  # 18:45
    return custom_scenario(
        name="EV charger offline 18:00–18:45",
        power_limit_kw=14.0,
        ev_offline=(start, end),
        note="The EV charger is uncommandable for 45 minutes. The controller reserves its "
        "last power and defers other loads until it reconnects.",
    )


def infeasible() -> Scenario:
    """Over-tight 8 kW limit on a very hot evening — honestly infeasible.

    The AC must run to hold comfort and the EV/water heater still owe energy before
    their deadlines, but 8 kW cannot cover all of it. The controller reports minutes
    over the limit and/or temperature violations instead of hiding them.
    """
    # Demand 40 kWh into the EV but give it an early 23:00 deadline. At 7.2 kW the EV
    # needs ~333 min of full power; combined with a hot-evening AC load and base load
    # under an 8 kW cap, the deadline cannot be met without breaching the limit. The
    # controller runs the EV flat out as slack hits zero and reports the breach.
    return custom_scenario(
        name="Infeasible (8 kW, early EV deadline)",
        power_limit_kw=8.0,
        peak_outdoor_c=34.0,
        ev_kwh=40.0,
        ev_deadline_min=7 * 60,  # 23:00 — too soon for 40 kWh under an 8 kW cap
        note="A hard case: a large EV charge is due early (23:00) under a tight 8 kW cap on "
        "a hot evening. It cannot all fit. The controller runs the EV at full power as its "
        "slack reaches zero and reports the minutes over the limit honestly.",
    )


# Registry for the dashboard scenario picker.
SCENARIOS = {
    "Hot evening (14 kW)": hot_evening,
    "Tight limit (11 kW)": tight_limit,
    "EV offline 18:00–18:45": ev_offline,
    "Infeasible (8 kW, early EV deadline)": infeasible,
}


def scenarios() -> dict[str, "callable"]:
    """Return the scenario registry: display name -> zero-arg builder."""
    return dict(SCENARIOS)
