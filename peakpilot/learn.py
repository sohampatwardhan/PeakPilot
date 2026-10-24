"""Learned models as analysis next to the scheduler (SciPy; all values SIMULATED).

Two pieces, both from the studies in ``studies/``:

* **Thermal calibration** (:func:`fit_thermal`). Fit the engine's first-order room
  model to thermostat-style telemetry (room °C, outdoor °C, AC kW per minute). The
  model is linear in ``a = 1/(R*C)`` and ``b = eta/C``::

      room[t+1] = room[t] + a * (outdoor[t] - room[t]) - b * ac_kw[t]

  so an ordinary least-squares fit on one-step differences ("equation error") gives a
  fast first estimate. It then seeds an output-error fit that simulates the whole
  series and matches it (``scipy.optimize.least_squares``), which is robust to sensor
  noise where equation error is biased.
* **Forecast cost** (:func:`forecast_cost`). Plan with the perfect-foresight LP
  (:func:`peakpilot.optimal.solve`) on a *wrong* base-load / outdoor forecast, then
  play that plan open-loop against the true evening: what peak and comfort would a
  forecast-driven planner really get?

Neither piece controls anything. PeakPilot's control stays the deterministic,
reactive scheduler in ``engine.py``, which this module only calls. Every random draw
is seeded, so identical inputs give identical outputs. Only this module and
``optimal.py`` import SciPy. Units follow the engine: kW, kWh, °C, minutes from 16:00.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
from scipy import linalg
from scipy.optimize import least_squares

from . import optimal
from .engine import WINDOW_MINUTES, DeviceKind, Scenario, ThermalParams, _step_room_temp, run_coordinated

SEED = 20261024
"""Default seed for every simulated noise draw in this module."""

_MIN_POINTS = 60  # one hour of one-minute telemetry
# Output-error search box for (a, b, start °C): wide enough for any plausible room.
_OE_LOWER = (1e-4, 1e-4, 0.0)
_OE_UPPER = (1.0, 5.0, 60.0)


# --- Thermal calibration -----------------------------------------------------


@dataclass(frozen=True)
class ThermalFit:
    """A room model fitted to telemetry (SIMULATED unless the telemetry is real).

    Attributes
    ----------
    params: Fitted :class:`~peakpilot.engine.ThermalParams`. Temperature data pins
        down only ``a`` and ``b``, so ``c`` is kept from the prior and
        ``r = 1/(a*c)``, ``eta = b*c``; ``comfort_c`` and ``start_c`` are the prior's.
    a: Fitted heat-exchange rate per minute, ``1/(R*C)``.
    b: Fitted cooling effect, °C per kW per minute, ``eta/C``.
    start_c: Fitted room temperature at the first sample, °C.
    rmse_c: In-sample free-run RMSE in °C: simulate from ``start_c`` with the
        measured outdoor and AC series and compare with the measured room series.
    ac_on_min: Minutes with the AC drawing power in the telemetry.
    method: How the parameters were found, in plain language.
    """

    params: ThermalParams
    a: float
    b: float
    start_c: float
    rmse_c: float
    ac_on_min: int
    method: str


def _free_run(a: float, b: float, start_c: float, outdoor: np.ndarray, ac_kw: np.ndarray) -> np.ndarray:
    temps = np.empty(len(outdoor))
    temps[0] = start_c
    for t in range(len(outdoor) - 1):
        temps[t + 1] = temps[t] + a * (outdoor[t] - temps[t]) - b * ac_kw[t]
    return temps


def fit_thermal(
    room_c: list[float],
    outdoor_c: list[float],
    ac_kw: list[float],
    prior: ThermalParams = ThermalParams(),
) -> ThermalFit:
    """Fit the engine's room model to one-minute telemetry.

    ``room_c[t]`` is the room temperature at the start of minute ``t``, and
    ``outdoor_c[t]`` and ``ac_kw[t]`` act during that minute, as in the engine.
    Equation-error OLS (``scipy.linalg.lstsq``) seeds an output-error fit of
    ``(a, b, start_c)`` (``scipy.optimize.least_squares``). If the output-error fit
    does not converge, the equation-error estimate is returned and ``method`` says
    so. Deterministic.

    Raises ``ValueError`` if the series differ in length, have fewer than 60 points,
    contain non-finite values or negative AC power, or the AC never runs (cooling
    must be seen to be measured).
    """
    room = np.asarray(room_c, dtype=float)
    out = np.asarray(outdoor_c, dtype=float)
    ac = np.asarray(ac_kw, dtype=float)
    if not len(room) == len(out) == len(ac):
        raise ValueError("room_c, outdoor_c and ac_kw must have the same length")
    if len(room) < _MIN_POINTS:
        raise ValueError(f"need at least {_MIN_POINTS} one-minute points, got {len(room)}")
    if not (np.isfinite(room).all() and np.isfinite(out).all() and np.isfinite(ac).all()):
        raise ValueError("telemetry contains non-finite values")
    if (ac < 0).any():
        raise ValueError("ac_kw must be >= 0")
    ac_on = int((ac[:-1] > 0).sum())
    if ac_on == 0:
        raise ValueError("the AC never runs in this telemetry, so its cooling effect cannot be fitted")

    design = np.column_stack([out[:-1] - room[:-1], -ac[:-1]])
    (a_ee, b_ee), *_ = linalg.lstsq(design, np.diff(room))
    seed = np.clip([a_ee, b_ee, room[0]], _OE_LOWER, _OE_UPPER)
    res = least_squares(
        lambda x: _free_run(x[0], x[1], x[2], out, ac) - room,
        x0=seed,
        bounds=(_OE_LOWER, _OE_UPPER),
    )
    if res.status > 0:
        a, b, start = (float(v) for v in res.x)
        method = "output-error least squares, seeded by equation-error OLS"
    else:
        a, b, start = float(seed[0]), float(seed[1]), float(seed[2])
        method = f"equation-error OLS only (output-error fit did not converge: {res.message})"
    rmse = float(np.sqrt(np.mean((_free_run(a, b, start, out, ac) - room) ** 2)))
    params = dataclasses.replace(prior, r=1.0 / (a * prior.c), eta=b * prior.c)
    return ThermalFit(params, a, b, start, rmse, ac_on, method)


def simulated_telemetry(
    scenario: Scenario,
    noise_c: float = 0.2,
    seed: int = SEED,
) -> tuple[list[float], list[float], list[float]]:
    """``(room °C, outdoor °C, AC kW)`` per minute from the coordinated run (SIMULATED).

    Stands in for a building's thermostat and AC meter: the engine's coordinated
    run supplies the true series, and seeded Gaussian sensor noise of ``noise_c``
    (std, °C) is added to the room reading only.
    """
    if noise_c < 0:
        raise ValueError("noise_c must be >= 0")
    run = run_coordinated(scenario)
    ac_id = next(d.id for d in scenario.devices if d.kind is DeviceKind.AIR_CONDITIONER)
    noise = np.random.default_rng(seed).normal(0.0, 1.0, WINDOW_MINUTES) * noise_c
    room = (np.asarray(run.room_c) + noise).tolist()
    return room, list(scenario.outdoor_c), list(run.per_device_kw[ac_id])


# --- Forecast cost -----------------------------------------------------------


@dataclass(frozen=True)
class ForecastError:
    """How a day-ahead forecast differs from the true evening.

    Attributes
    ----------
    scale: Base-load multiplier, 0.8-1.2 (1.1 = forecast 10 % too high).
    shift_min: Base-load timing error in minutes, -60..60; positive = forecast late.
    noise_kw: Std of seeded Gaussian noise on the base-load forecast, 0-0.5 kW.
    outdoor_bias_c: Outdoor-temperature forecast error, -3..3 °C; negative = too cool.
    seed: Seed for the noise draw.
    """

    scale: float = 1.0
    shift_min: int = 0
    noise_kw: float = 0.0
    outdoor_bias_c: float = 0.0
    seed: int = SEED

    def __post_init__(self) -> None:
        if not 0.8 <= self.scale <= 1.2:
            raise ValueError("scale must be in [0.8, 1.2]")
        if not -60 <= self.shift_min <= 60:
            raise ValueError("shift_min must be in [-60, 60]")
        if not 0.0 <= self.noise_kw <= 0.5:
            raise ValueError("noise_kw must be in [0, 0.5]")
        if not -3.0 <= self.outdoor_bias_c <= 3.0:
            raise ValueError("outdoor_bias_c must be in [-3, 3]")


@dataclass(frozen=True)
class ForecastCost:
    """An LP plan made on a forecast, played against the true evening (SIMULATED).

    Attributes
    ----------
    status: The planning LP's status (``"optimal"``, ``"infeasible"``, ``"error"``).
    planned_peak_kw: Peak the plan expects on the forecast, or ``None``.
    realized_peak_kw: Peak of true base load plus the planned device power, or ``None``.
    comfort_violation_min: Minutes the true room exceeds ``comfort_c`` when the
        planned AC power meets the true outdoor temperature, or ``None``.
    """

    status: str
    planned_peak_kw: float | None
    realized_peak_kw: float | None
    comfort_violation_min: int | None


def _shift(series: np.ndarray, minutes: int) -> np.ndarray:
    """Move a series later (``minutes > 0``) or earlier, padding with the edge value."""
    if minutes > 0:
        return np.concatenate([np.full(minutes, series[0]), series[:-minutes]])
    if minutes < 0:
        return np.concatenate([series[-minutes:], np.full(-minutes, series[-1])])
    return series


def forecast_cost(scenario: Scenario, error: ForecastError) -> ForecastCost:
    """Plan on a forecast with ``error`` and score the plan against ``scenario``.

    The forecast base load is the true one scaled, shifted, and given seeded noise
    (floored at 0 kW). The forecast outdoor series is the true one plus the bias.
    :func:`peakpilot.optimal.solve` plans every device on that forecast. The plan is
    then played open-loop: realized demand is true base load plus planned device
    power, and the room is re-simulated with the engine's thermal step, the true
    outdoor series and the planned AC power. No reactive correction is applied;
    that is the point of the comparison. Deterministic for a given ``error.seed``.
    """
    base = np.asarray(scenario.base_load, dtype=float)
    fc_base = _shift(base * error.scale, error.shift_min)
    if error.noise_kw:
        fc_base = fc_base + np.random.default_rng(error.seed).normal(0.0, 1.0, len(base)) * error.noise_kw
    fc_out = np.asarray(scenario.outdoor_c, dtype=float) + error.outdoor_bias_c
    plan = optimal.solve(
        dataclasses.replace(
            scenario,
            base_load=tuple(float(x) for x in np.maximum(fc_base, 0.0)),
            outdoor_c=tuple(float(x) for x in fc_out),
        )
    )
    if plan.status != "optimal":
        return ForecastCost(plan.status, None, None, None)

    devices_kw = np.sum([np.asarray(v) for v in plan.per_device_kw.values()], axis=0)
    realized = base + devices_kw
    ac = next((d for d in scenario.devices if d.kind is DeviceKind.AIR_CONDITIONER), None)
    ac_kw = plan.per_device_kw[ac.id] if ac is not None else [0.0] * WINDOW_MINUTES
    thermal = scenario.thermal
    room = thermal.start_c
    violations = 0
    for t in range(WINDOW_MINUTES):
        if room > thermal.comfort_c + 1e-9:
            violations += 1
        room = _step_room_temp(room, scenario.outdoor_c[t], ac_kw[t], thermal)
    return ForecastCost("optimal", plan.peak_kw, float(realized.max()), violations)
