"""PeakPilot simulation engine — pure Python standard library.

This module is the single source of truth for PeakPilot's control logic. It
simulates one building from 16:00 to 08:00 (the next day) in one-minute steps and
runs the same workload twice: once uncoordinated (every device pulls full power
whenever it has work, ignoring the limit) and once coordinated by a deterministic
least-slack-first scheduler that holds the building under a power limit while
respecting energy requirements, deadlines, minimum run times, and a room-temperature
comfort constraint.

Units and conventions
----------------------
* Power is in kilowatts (``*_kw``), energy in kilowatt-hours (``*_kwh``),
  temperature in degrees Celsius (``*_c``), and time in minutes from the start of
  the window (``*_min``; minute 0 == 16:00).
* ``energy_kwh = power_kw * (minutes / 60)``.
* The control path contains no randomness: identical ``Scenario`` inputs always
  produce identical results.

All device telemetry produced here is SIMULATED. Nothing in this module connects to
or controls real electrical equipment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable

# --- Time window ------------------------------------------------------------

START_MINUTE = 16 * 60  # 16:00, in minutes past midnight
WINDOW_MINUTES = 16 * 60  # 16:00 -> 08:00 next day == 960 one-minute steps


def clock(step_min: int) -> str:
    """Return the wall-clock ``HH:MM`` label for a step offset into the window.

    ``step_min`` is minutes since the window start (minute 0 == 16:00). The label
    wraps past midnight so step 480 reads ``00:00``.
    """
    absolute = (START_MINUTE + step_min) % (24 * 60)
    return f"{absolute // 60:02d}:{absolute % 60:02d}"


# --- Devices ----------------------------------------------------------------


class DeviceKind(str, Enum):
    """The three flexible loads PeakPilot coordinates."""

    EV = "ev"
    WATER_HEATER = "water_heater"
    AIR_CONDITIONER = "air_conditioner"


@dataclass(frozen=True)
class DeviceSpec:
    """Static configuration for one simulated device.

    Attributes
    ----------
    id: Stable identifier, e.g. ``"ev-1"``.
    kind: Which :class:`DeviceKind` this is.
    max_kw: Maximum power draw in kW.
    min_run_min: Once switched on, the device stays on at least this many minutes
        (relay-friendly; 0 for the continuously throttleable EV charger).
    target_kwh: Energy the device must deliver before its deadline (EV, water
        heater). ``None`` for the AC, whose duty is governed by the thermal model.
    deadline_min: Minute by which ``target_kwh`` must be met. ``None`` for the AC.
    offline_window: Optional ``(start_min, end_min)`` during which the device is
        offline/uncommandable. ``None`` means always online.
    commands: Supported control commands, surfaced to the UI / a future real device.
    """

    id: str
    kind: DeviceKind
    max_kw: float
    min_run_min: int = 0
    target_kwh: float | None = None
    deadline_min: int | None = None
    offline_window: tuple[int, int] | None = None
    commands: tuple[str, ...] = ("set_power", "on", "off")

    def is_online_at(self, step_min: int) -> bool:
        """Return whether the device is reachable at ``step_min`` (SIMULATED)."""
        if self.offline_window is None:
            return True
        start, end = self.offline_window
        return not (start <= step_min < end)


@dataclass
class DeviceState:
    """Mutable per-minute runtime state for a device (all values SIMULATED)."""

    spec: DeviceSpec
    power_kw: float = 0.0
    delivered_kwh: float = 0.0
    online: bool = True
    last_update_min: int = 0
    run_remaining_min: int = 0  # minimum-run lock countdown

    @property
    def id(self) -> str:
        return self.spec.id

    def remaining_kwh(self) -> float:
        """Energy still owed before the deadline (0 for AC / once met)."""
        if self.spec.target_kwh is None:
            return 0.0
        return max(0.0, self.spec.target_kwh - self.delivered_kwh)


# --- Scenario ---------------------------------------------------------------


@dataclass(frozen=True)
class ThermalParams:
    """First-order RC room model parameters (illustrative, not a real building).

    ``room_c[t+1] = room_c[t] + (1/C) * ((outdoor_c - room_c)/R - cooling_kw*eta)``
    evaluated per one-minute step. Values are tuned so a hot evening pushes the
    room above ``comfort_c`` without cooling, while the AC can hold it under the
    limit when the scheduler gives it priority.
    """

    r: float = 1.6  # thermal resistance (°C per kW of heat flow)
    c: float = 9.0  # thermal capacitance (kWh per °C), per minute step scaled by dt
    eta: float = 3.2  # cooling effectiveness (°C·C per kW·min equivalent)
    comfort_c: float = 25.0
    start_c: float = 24.0


@dataclass(frozen=True)
class Scenario:
    """A fully specified, reproducible simulation input.

    Both the baseline and coordinated runs for a scenario use these identical
    workloads, initial conditions, and environmental inputs, so any peak reduction
    comes from scheduling rather than from doing less work.
    """

    name: str
    power_limit_kw: float
    devices: tuple[DeviceSpec, ...]
    base_load: tuple[float, ...]  # length WINDOW_MINUTES, kW, uncontrollable
    outdoor_c: tuple[float, ...]  # length WINDOW_MINUTES, °C
    thermal: ThermalParams = ThermalParams()
    note: str = ""


# --- Results ----------------------------------------------------------------


@dataclass
class DecisionEntry:
    """One plain-language decision-log line, emitted only on a state change."""

    minute: int
    device: str
    message: str

    def as_row(self) -> dict:
        return {"time": clock(self.minute), "device": self.device, "message": self.message}


@dataclass
class RunResult:
    """Outcome of a single run (baseline or coordinated)."""

    label: str
    minutes: list[int]
    total_kw: list[float]
    per_device_kw: dict[str, list[float]]
    room_c: list[float]
    power_limit_kw: float
    peak_kw: float
    total_kwh: float
    per_device_kwh: dict[str, float]
    tasks_met: dict[str, bool]
    unmet_kwh: dict[str, float]
    minutes_over_limit: int
    temp_violation_min: int
    decision_log: list[DecisionEntry]

    def all_tasks_met(self) -> bool:
        return all(self.tasks_met.values())


@dataclass
class CompareResult:
    """Baseline vs coordinated comparison for one scenario."""

    scenario_name: str
    power_limit_kw: float
    baseline: RunResult
    coordinated: RunResult
    comfort_c: float

    @property
    def peak_reduction_pct(self) -> float:
        if self.baseline.peak_kw <= 0:
            return 0.0
        return 100.0 * (self.baseline.peak_kw - self.coordinated.peak_kw) / self.baseline.peak_kw

    def to_json_dict(self) -> dict:
        """Serialize everything a front end needs (Streamlit now, e.g. React later)."""

        def run(r: RunResult) -> dict:
            return {
                "label": r.label,
                "minutes": r.minutes,
                "clock": [clock(m) for m in r.minutes],
                "total_kw": r.total_kw,
                "per_device_kw": r.per_device_kw,
                "room_c": r.room_c,
                "power_limit_kw": r.power_limit_kw,
                "peak_kw": r.peak_kw,
                "total_kwh": r.total_kwh,
                "per_device_kwh": r.per_device_kwh,
                "tasks_met": r.tasks_met,
                "unmet_kwh": r.unmet_kwh,
                "minutes_over_limit": r.minutes_over_limit,
                "temp_violation_min": r.temp_violation_min,
                "decision_log": [d.as_row() for d in r.decision_log],
            }

        return {
            "scenario_name": self.scenario_name,
            "power_limit_kw": self.power_limit_kw,
            "comfort_c": self.comfort_c,
            "peak_reduction_pct": self.peak_reduction_pct,
            "baseline": run(self.baseline),
            "coordinated": run(self.coordinated),
        }


# --- Thermal step -----------------------------------------------------------


def _step_room_temp(room_c: float, outdoor_c: float, cooling_kw: float, p: ThermalParams) -> float:
    """Advance the room temperature one minute (SIMULATED, illustrative model)."""
    dt = 1.0 / 60.0  # one minute expressed in hours
    heat_gain = (outdoor_c - room_c) / p.r  # kW flowing in from outside
    net = heat_gain - cooling_kw * p.eta
    return room_c + (net / p.c) * dt * 60.0  # scaled so dynamics are visible per minute


# --- Core simulation --------------------------------------------------------


def _new_states(scenario: Scenario) -> dict[str, DeviceState]:
    return {d.id: DeviceState(spec=d) for d in scenario.devices}


def _ac_spec(scenario: Scenario) -> DeviceSpec | None:
    for d in scenario.devices:
        if d.kind is DeviceKind.AIR_CONDITIONER:
            return d
    return None


def _finalize(
    label: str,
    scenario: Scenario,
    minutes: list[int],
    total_kw: list[float],
    per_device_kw: dict[str, list[float]],
    room_c: list[float],
    states: dict[str, DeviceState],
    decision_log: list[DecisionEntry],
) -> RunResult:
    peak_kw = max(total_kw) if total_kw else 0.0
    total_kwh = sum(total_kw) / 60.0
    per_device_kwh = {sid: s.delivered_kwh for sid, s in states.items()}
    tasks_met: dict[str, bool] = {}
    unmet_kwh: dict[str, float] = {}
    for sid, s in states.items():
        if s.spec.target_kwh is None:
            continue
        # A deadline is met only by energy drawn before it. Energy delivered after the
        # deadline still shows in per_device_kwh but does not count as meeting the task.
        assert s.spec.deadline_min is not None
        by_deadline = 0.0
        for p in per_device_kw[sid][: s.spec.deadline_min]:
            by_deadline += p / 60.0
        unmet = max(0.0, s.spec.target_kwh - by_deadline)
        unmet_kwh[sid] = unmet
        tasks_met[sid] = unmet <= 1e-6
    minutes_over_limit = sum(1 for v in total_kw if v > scenario.power_limit_kw + 1e-9)
    temp_violation_min = sum(1 for t in room_c if t > scenario.thermal.comfort_c + 1e-9)
    return RunResult(
        label=label,
        minutes=minutes,
        total_kw=total_kw,
        per_device_kw=per_device_kw,
        room_c=room_c,
        power_limit_kw=scenario.power_limit_kw,
        peak_kw=peak_kw,
        total_kwh=total_kwh,
        per_device_kwh=per_device_kwh,
        tasks_met=tasks_met,
        unmet_kwh=unmet_kwh,
        minutes_over_limit=minutes_over_limit,
        temp_violation_min=temp_violation_min,
        decision_log=decision_log,
    )


def _log(log: list[DecisionEntry], minute: int, device: str, message: str) -> None:
    log.append(DecisionEntry(minute=minute, device=device, message=message))


def _minutes_needed(remaining_kwh: float, max_kw: float) -> int:
    """Whole minutes of full-power run needed to deliver ``remaining_kwh``."""
    if remaining_kwh <= 0 or max_kw <= 0:
        return 0
    return math.ceil(remaining_kwh / max_kw * 60.0)


def run_baseline(scenario: Scenario) -> RunResult:
    """Uncoordinated run: every device pulls full power while it has work.

    The AC runs whenever the room is at or above the comfort limit. Energy tasks
    (EV, water heater) run flat-out until met. The power limit is ignored — this is
    the "everyone plugs in at once" baseline. Same workload/inputs as the
    coordinated run.
    """
    states = _new_states(scenario)
    minutes: list[int] = []
    total_kw: list[float] = []
    per_device_kw: dict[str, list[float]] = {sid: [] for sid in states}
    room_series: list[float] = []
    log: list[DecisionEntry] = []
    room_c = scenario.thermal.start_c

    for m in range(WINDOW_MINUTES):
        cooling_kw = 0.0
        for sid, s in states.items():
            spec = s.spec
            online = spec.is_online_at(m)
            prev_online = s.online
            s.online = online
            s.last_update_min = m if online else s.last_update_min
            if online != prev_online:
                _log(log, m, sid, "came online" if online else "went OFFLINE (SIMULATED)")

            if spec.kind is DeviceKind.AIR_CONDITIONER:
                # Baseline AC: reactive thermostat at the comfort limit.
                want_on = room_c >= scenario.thermal.comfort_c
                if s.run_remaining_min > 0:
                    want_on = True
                power = spec.max_kw if (want_on and online) else 0.0
                if power > 0 and s.power_kw == 0:
                    s.run_remaining_min = spec.min_run_min
                cooling_kw = power
            else:
                if online and s.remaining_kwh() > 0:
                    power = min(spec.max_kw, s.remaining_kwh() * 60.0)
                else:
                    power = 0.0

            s.power_kw = power
            s.delivered_kwh += power / 60.0
            if s.run_remaining_min > 0:
                s.run_remaining_min -= 1
            per_device_kw[sid].append(power)

        step_total = sum(s.power_kw for s in states.values()) + scenario.base_load[m]
        minutes.append(m)
        total_kw.append(step_total)
        room_series.append(room_c)
        room_c = _step_room_temp(room_c, scenario.outdoor_c[m], cooling_kw, scenario.thermal)

    return _finalize("Uncoordinated", scenario, minutes, total_kw, per_device_kw, room_series, states, log)


def run_coordinated(scenario: Scenario) -> RunResult:
    """Coordinated run: deterministic least-slack-first scheduler under the limit.

    Each minute the scheduler: reserves headroom for the uncontrollable base load
    and any offline device (assumed to hold its last commanded power); gives the AC
    priority when the room nears the comfort limit; then allocates the remaining
    headroom to energy tasks in ascending slack order. A task whose slack has run
    out runs at full power even if that breaches the limit, and the breach is
    logged. Minimum run times are honored. The log records only state changes.
    """
    states = _new_states(scenario)
    minutes: list[int] = []
    total_kw: list[float] = []
    per_device_kw: dict[str, list[float]] = {sid: [] for sid in states}
    room_series: list[float] = []
    log: list[DecisionEntry] = []
    room_c = scenario.thermal.start_c
    thermal = scenario.thermal
    ac_spec = _ac_spec(scenario)

    def slack_of(s: DeviceState, now: int) -> int:
        """Minutes of spare time: time to deadline minus full-power minutes needed."""
        assert s.spec.deadline_min is not None
        need = _minutes_needed(s.remaining_kwh(), s.spec.max_kw)
        return (s.spec.deadline_min - now) - need

    for m in range(WINDOW_MINUTES):
        limit = scenario.power_limit_kw
        committed = scenario.base_load[m]
        cooling_kw = 0.0

        # Refresh online state and disclose offline transitions.
        for sid, s in states.items():
            online = s.spec.is_online_at(m)
            prev_online = s.online
            s.online = online
            if online != prev_online:
                if online:
                    _log(log, m, sid, "reconnected; resuming control")
                else:
                    _log(
                        log,
                        m,
                        sid,
                        f"OFFLINE — holding last power {s.power_kw:.1f} kW, reserving headroom (SIMULATED)",
                    )
            if online:
                s.last_update_min = m

        # ---- Pass 1: commit forced loads (cannot be throttled this minute) ----
        # (a) Offline devices: assumed to hold their last commanded power.
        for s in states.values():
            if not s.online:
                committed += s.power_kw

        # (b) AC priority: cool when the room nears the comfort limit, honoring min run.
        if ac_spec is not None:
            ac = states[ac_spec.id]
            if ac.online:
                # Start cooling a little before the comfort limit so the room does not
                # overshoot; 0.8 °C of pre-emptive margin keeps feasible scenarios clean.
                near_limit = room_c >= thermal.comfort_c - 0.8
                want_on = near_limit or ac.run_remaining_min > 0
                if want_on:
                    if ac.power_kw == 0:
                        ac.run_remaining_min = ac.spec.min_run_min
                        _log(log, m, ac.id, "cooling ON — room near comfort limit (priority)")
                    ac.power_kw = ac.spec.max_kw
                else:
                    if ac.power_kw > 0 and ac.run_remaining_min <= 0:
                        _log(log, m, ac.id, "cooling OFF — room within comfort band")
                    ac.power_kw = 0.0
                if ac.run_remaining_min > 0:
                    ac.run_remaining_min -= 1
                cooling_kw = ac.power_kw
                committed += ac.power_kw

        # (c) Water heater already inside its minimum run: must keep going at full power.
        wh = next((s for s in states.values() if s.spec.kind is DeviceKind.WATER_HEATER), None)
        wh_locked = False
        if wh is not None and wh.online and wh.run_remaining_min > 0 and wh.remaining_kwh() > 0:
            wh.power_kw = min(wh.spec.max_kw, wh.remaining_kwh() * 60.0)
            committed += wh.power_kw
            wh.run_remaining_min -= 1
            wh_locked = True  # already committed this minute; skip in pass 2

        # ---- Pass 2: distribute remaining headroom, least-slack-first ----
        startable = [
            s
            for s in states.values()
            if s.online
            and s.spec.kind in (DeviceKind.EV, DeviceKind.WATER_HEATER)
            and s.remaining_kwh() > 0
            and not (s is wh and wh_locked)
        ]
        startable.sort(key=lambda s: (slack_of(s, m), s.id))

        for s in startable:
            spec = s.spec
            slack = slack_of(s, m)
            headroom = limit - committed
            full = min(spec.max_kw, s.remaining_kwh() * 60.0)

            if slack <= 0:
                # Out of slack: run full power even if it breaches the limit (logged).
                power = full
                if power > headroom + 1e-9:
                    _log(log, m, s.id, "deadline forces full power — exceeding limit (SIMULATED)")
            elif headroom <= 1e-9:
                power = 0.0
                if s.power_kw > 0:
                    _log(log, m, s.id, "paused to hold building under power limit")
            else:
                if spec.kind is DeviceKind.WATER_HEATER:
                    # On/off device: only start if the limit will hold for the WHOLE
                    # minimum run. Forecast base load plus a conservative AC reservation
                    # (its max kW while the room can still demand cooling) across the
                    # min-run window; also keep room for anything already committed now.
                    ac_reserve = ac_spec.max_kw if ac_spec is not None else 0.0
                    worst_base = max(
                        scenario.base_load[t]
                        for t in range(m, min(m + spec.min_run_min, WINDOW_MINUTES))
                    )
                    # Headroom that must exist for every minute of the run.
                    forecast_floor = worst_base + ac_reserve + spec.max_kw
                    fits_now = headroom >= spec.max_kw - 1e-9
                    fits_run = forecast_floor <= limit + 1e-9
                    if fits_now and fits_run:
                        power = min(spec.max_kw, s.remaining_kwh() * 60.0)
                        s.run_remaining_min = max(0, spec.min_run_min - 1)
                        _log(log, m, s.id, f"heating ON (min run {spec.min_run_min} min)")
                    else:
                        power = 0.0
                        if not fits_run:
                            # Too tight to guarantee the whole run; wait for a quieter window.
                            pass
                else:
                    # EV: continuously throttleable, absorbs remaining headroom.
                    power = min(full, headroom)
                    if power < full - 1e-9 and s.power_kw >= full - 1e-9:
                        _log(log, m, s.id, "throttled to fit power limit")
                    elif s.power_kw == 0 and power > 0:
                        _log(log, m, s.id, "resumed within available headroom")

            s.power_kw = power
            committed += power

        # ---- Commit energy + record series for every device (consistent order) ----
        for sid in per_device_kw:
            s = states[sid]
            is_task = s.spec.kind in (DeviceKind.EV, DeviceKind.WATER_HEATER)
            if s.remaining_kwh() <= 0 and is_task and s.power_kw > 0:
                _log(log, m, sid, "task complete — stopping")
                s.power_kw = 0.0
            elif is_task and not s.online:
                # An offline device stops on its own once its target is reached, so it
                # never draws more than it still owes (the controller still reserved its
                # full last power above, because it cannot see the device).
                s.power_kw = min(s.power_kw, s.remaining_kwh() * 60.0)
            s.delivered_kwh += s.power_kw / 60.0
            per_device_kw[sid].append(s.power_kw)

        minutes.append(m)
        # Report what the building actually drew. `committed` is the controller's plan,
        # which can include headroom reserved for an offline device that has stopped.
        total_kw.append(sum(s.power_kw for s in states.values()) + scenario.base_load[m])
        room_series.append(room_c)
        room_c = _step_room_temp(room_c, scenario.outdoor_c[m], cooling_kw, thermal)

    return _finalize("PeakPilot coordinated", scenario, minutes, total_kw, per_device_kw, room_series, states, log)


def compare(scenario: Scenario) -> CompareResult:
    """Run baseline and coordinated simulations for ``scenario`` and compare them."""
    baseline = run_baseline(scenario)
    coordinated = run_coordinated(scenario)
    return CompareResult(
        scenario_name=scenario.name,
        power_limit_kw=scenario.power_limit_kw,
        baseline=baseline,
        coordinated=coordinated,
        comfort_c=scenario.thermal.comfort_c,
    )
