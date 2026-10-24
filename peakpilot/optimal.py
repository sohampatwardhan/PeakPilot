"""Perfect-foresight peak benchmark for a PeakPilot scenario (SciPy LP).

This module answers "how close to optimal is the coordinated scheduler?". It turns
an engine :class:`~peakpilot.engine.Scenario` into one linear program (LP) and
solves it with ``scipy.optimize.linprog(method="highs")``. The LP minimizes the
peak building demand in kW over the same 960 one-minute steps, subject to the same
work the engine must do: each energy device delivers exactly its ``target_kwh``
before its ``deadline_min``, device power stays in ``[0, max_kw]``, an offline
device holds its last power, and the room follows the engine's thermal model and
stays at or below ``comfort_c``.

It is a benchmark, not a controller. It does not change ``engine.py`` and does not
schedule anything the dashboard shows as PeakPilot's behavior. Two caveats apply
to every result and the dashboard states both:

* **Perfect foresight.** The LP sees the whole evening's base load and outdoor
  temperature in advance. The engine decides minute by minute.
* **Lower bound.** The LP relaxes rules the engine enforces (see
  :data:`RELAXATIONS`), so its peak is a lower bound on the achievable peak, not
  a schedule a real device could necessarily follow.

Units follow the engine: power in kW (``*_kw``), energy in kWh (``*_kwh``),
temperature in °C (``*_c``), time in minutes from 16:00. All values are SIMULATED.
This module is the only place in PeakPilot that imports SciPy.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
from scipy import sparse
from scipy.optimize import linprog

from .engine import WINDOW_MINUTES, DeviceKind, RunResult, Scenario

logger = logging.getLogger(__name__)

RELAXATIONS: tuple[str, ...] = (
    "Water heater: the engine switches it fully on (4.5 kW) or off with a 15-minute "
    "minimum run. The LP lets it draw any power from 0 to its maximum.",
    "Air conditioner: the engine switches it fully on (3.5 kW) or off with a 10-minute "
    "minimum run. The LP lets it draw any power from 0 to its maximum.",
    "An offline air conditioner: the engine gives no cooling while it is offline, but "
    "the LP counts its held power as cooling. No named scenario has an offline AC.",
)
"""Plain-language list of the engine rules the LP relaxes (why it is a lower bound)."""

_FEASIBILITY_TOL = 1e-6  # kW / kWh tolerance for comparisons against the engine


@dataclass
class OptimalResult:
    """Outcome of one perfect-foresight LP solve (all values SIMULATED).

    Attributes
    ----------
    scenario_name: ``Scenario.name`` of the solved scenario.
    status: ``"optimal"``, ``"infeasible"`` (no schedule meets every deadline and the
        comfort limit), or ``"error"`` (solver stopped for another reason).
    message: Solver message; most useful when ``status == "error"``.
    peak_kw: Lowest achievable peak building demand in kW under the LP, or ``None``
        unless ``status == "optimal"``.
    total_kw: Building demand per minute in kW (base load plus devices). Empty unless
        optimal.
    per_device_kw: Device id -> power per minute in kW. Empty unless optimal.
    room_c: Room temperature per minute in °C, ``room_c[0] == thermal.start_c``.
        Empty unless optimal.
    is_lower_bound: ``True`` because the LP relaxes engine rules (see ``relaxations``).
    relaxations: The relaxed rules, in plain language.
    solve_time_s: Wall-clock seconds to build and solve the LP. Diagnostics only;
        excluded from :meth:`to_json_dict` so identical scenarios compare equal.
    """

    scenario_name: str
    status: str
    message: str
    peak_kw: float | None
    total_kw: list[float] = field(default_factory=list)
    per_device_kw: dict[str, list[float]] = field(default_factory=dict)
    room_c: list[float] = field(default_factory=list)
    is_lower_bound: bool = True
    relaxations: tuple[str, ...] = RELAXATIONS
    solve_time_s: float = 0.0

    def to_json_dict(self) -> dict:
        """Serialize every field except ``solve_time_s`` (which varies run to run)."""
        return {
            "scenario_name": self.scenario_name,
            "status": self.status,
            "message": self.message,
            "peak_kw": self.peak_kw,
            "total_kw": self.total_kw,
            "per_device_kw": self.per_device_kw,
            "room_c": self.room_c,
            "is_lower_bound": self.is_lower_bound,
            "relaxations": list(self.relaxations),
        }


@dataclass
class Benchmark:
    """Coordinated run compared with the LP lower bound (all values SIMULATED).

    Attributes
    ----------
    optimal: The LP result.
    coordinated_peak_kw: Peak building demand of the coordinated run, in kW.
    power_limit_kw: The scenario's building power limit, in kW.
    gap_kw: ``coordinated_peak_kw - optimal.peak_kw`` in kW, or ``None`` unless the LP
        is optimal.
    gap_pct: ``100 * gap_kw / coordinated_peak_kw`` (0 when that peak is 0), or
        ``None`` unless the LP is optimal.
    limit_achievable: Whether the bound is at or under the power limit (within 1e-6
        kW), or ``None`` unless the LP is optimal. ``False`` means the limit cannot
        be met even with perfect foresight.
    coordinated_comparable: ``True`` when the coordinated run delivered every
        ``target_kwh`` before its ``deadline_min`` and had zero minutes above the
        comfort limit. Otherwise the coordinated run did different work and the
        comparison is not like-for-like.
    """

    optimal: OptimalResult
    coordinated_peak_kw: float
    power_limit_kw: float
    gap_kw: float | None
    gap_pct: float | None
    limit_achievable: bool | None
    coordinated_comparable: bool

    def to_json_dict(self) -> dict:
        """Serialize for any front end; the LP part omits ``solve_time_s``."""
        return {
            "optimal": self.optimal.to_json_dict(),
            "coordinated_peak_kw": self.coordinated_peak_kw,
            "power_limit_kw": self.power_limit_kw,
            "gap_kw": self.gap_kw,
            "gap_pct": self.gap_pct,
            "limit_achievable": self.limit_achievable,
            "coordinated_comparable": self.coordinated_comparable,
        }


def _validate(scenario: Scenario) -> None:
    """Raise ``ValueError`` for scenarios the LP (and the engine) cannot represent."""
    n = WINDOW_MINUTES
    if len(scenario.base_load) != n or len(scenario.outdoor_c) != n:
        raise ValueError(f"base_load and outdoor_c must each have {n} one-minute values")
    acs = [d for d in scenario.devices if d.kind is DeviceKind.AIR_CONDITIONER]
    if len(acs) > 1:
        raise ValueError("the engine models at most one air conditioner")
    for d in scenario.devices:
        if d.max_kw < 0:
            raise ValueError(f"{d.id}: max_kw must be >= 0")
        if d.kind is DeviceKind.AIR_CONDITIONER or d.target_kwh is None:
            continue
        if d.target_kwh < 0:
            raise ValueError(f"{d.id}: target_kwh must be >= 0")
        if d.deadline_min is None:
            raise ValueError(f"{d.id}: target_kwh needs a deadline_min")
        if not 0 <= d.deadline_min <= n:
            raise ValueError(f"{d.id}: deadline_min must be in [0, {n}]")


def solve(scenario: Scenario) -> OptimalResult:
    """Return the lowest peak kW any schedule could reach for ``scenario``.

    Variables are device power ``p[d, t]`` in kW, room temperature ``T[t]`` in °C,
    and the peak ``P`` in kW, for ``t = 0..959`` (minute 0 == 16:00). The LP
    minimizes ``P`` subject to:

    * ``base_load[t] + sum_d p[d, t] <= P`` for every minute;
    * ``0 <= p[d, t] <= max_kw``;
    * energy devices: ``sum_{t < deadline} p[d, t] / 60 == target_kwh`` and
      ``p[d, t] == 0`` from the deadline on (the engine does exactly this much work);
    * a device offline over ``[s, e)`` holds ``p[d, s-1]`` (0 if ``s == 0``), matching
      the engine's assumption, up to the deadline;
    * ``T[0] = start_c`` and ``T[t+1] = (1 - a) T[t] + a outdoor_c[t] - b p_ac[t]``
      with ``a = 1/(r c)`` and ``b = eta / c``, which is the engine's
      ``_step_room_temp`` with its one-minute step;
    * ``T[t] <= comfort_c`` (the engine enforces only an upper comfort limit).

    The power limit is not a constraint; :func:`benchmark` compares against it.
    Deterministic: no randomness, and HiGHS gives the same answer for the same
    input on the pinned SciPy build. Raises ``ValueError`` for malformed scenarios.
    """
    _validate(scenario)
    t0 = time.perf_counter()
    n = WINDOW_MINUTES
    devices = scenario.devices
    nd = len(devices)
    t_off = nd * n  # first room-temperature variable
    p_idx = t_off + n  # peak variable
    n_vars = p_idx + 1
    thermal = scenario.thermal
    a = 1.0 / (thermal.r * thermal.c)
    b = thermal.eta / thermal.c

    def pv(di: int, t: int) -> int:
        return di * n + t

    c = np.zeros(n_vars)
    c[p_idx] = 1.0

    lower = np.zeros(n_vars)
    upper = np.zeros(n_vars)

    # Peak rows: sum_d p[d, t] - P <= -base_load[t].
    ub_rows: list[int] = []
    ub_cols: list[int] = []
    ub_vals: list[float] = []
    for t in range(n):
        for di in range(nd):
            ub_rows.append(t)
            ub_cols.append(pv(di, t))
            ub_vals.append(1.0)
        ub_rows.append(t)
        ub_cols.append(p_idx)
        ub_vals.append(-1.0)
    a_ub = sparse.csr_array((ub_vals, (ub_rows, ub_cols)), shape=(n, n_vars))
    b_ub = -np.asarray(scenario.base_load, dtype=float)

    eq_rows: list[int] = []
    eq_cols: list[int] = []
    eq_vals: list[float] = []
    b_eq: list[float] = []

    def add_eq(terms: list[tuple[int, float]], rhs: float) -> None:
        row = len(b_eq)
        for col, val in terms:
            eq_rows.append(row)
            eq_cols.append(col)
            eq_vals.append(val)
        b_eq.append(rhs)

    ac_index: int | None = None
    for di, d in enumerate(devices):
        is_ac = d.kind is DeviceKind.AIR_CONDITIONER
        if is_ac:
            ac_index = di
        # Energy devices with no target never run in the engine.
        active_until = n
        if not is_ac:
            active_until = 0 if d.target_kwh is None else d.deadline_min
        upper[pv(di, 0) : pv(di, active_until)] = d.max_kw

        if not is_ac and d.target_kwh is not None:
            add_eq([(pv(di, t), 1.0 / 60.0) for t in range(active_until)], d.target_kwh)

        if d.offline_window is not None:
            start, end = d.offline_window
            start = max(0, start)
            end = min(end, active_until)
            if start == 0:
                upper[pv(di, 0) : pv(di, max(end, 0))] = 0.0
            else:
                for t in range(start, end):
                    add_eq([(pv(di, t), 1.0), (pv(di, start - 1), -1.0)], 0.0)

    # Thermal rows: T[t+1] - (1 - a) T[t] + b p_ac[t] = a outdoor_c[t].
    for t in range(n - 1):
        terms = [(t_off + t + 1, 1.0), (t_off + t, -(1.0 - a))]
        if ac_index is not None:
            terms.append((pv(ac_index, t), b))
        add_eq(terms, a * scenario.outdoor_c[t])

    lower[t_off : t_off + n] = -np.inf
    upper[t_off : t_off + n] = thermal.comfort_c
    lower[t_off] = upper[t_off] = thermal.start_c
    lower[p_idx], upper[p_idx] = -np.inf, np.inf

    a_eq = sparse.csr_array((eq_vals, (eq_rows, eq_cols)), shape=(len(b_eq), n_vars))
    res = linprog(
        c,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=np.asarray(b_eq),
        bounds=np.column_stack([lower, upper]),
        method="highs",
    )
    elapsed = time.perf_counter() - t0

    # linprog status: 0 optimal, 1 iteration limit, 2 infeasible, 3 unbounded,
    # 4 numerical difficulties.
    if res.status == 2:
        return OptimalResult(scenario.name, "infeasible", res.message, None, solve_time_s=elapsed)
    if res.status != 0:
        logger.warning("optimal benchmark solver stopped: status %s, %s", res.status, res.message)
        return OptimalResult(scenario.name, "error", res.message, None, solve_time_s=elapsed)

    x = res.x
    per_device_kw = {d.id: x[pv(di, 0) : pv(di, n)].tolist() for di, d in enumerate(devices)}
    total = np.asarray(scenario.base_load, dtype=float)
    for di in range(nd):
        total = total + x[pv(di, 0) : pv(di, n)]
    return OptimalResult(
        scenario_name=scenario.name,
        status="optimal",
        message=res.message,
        peak_kw=float(res.fun),
        total_kw=total.tolist(),
        per_device_kw=per_device_kw,
        room_c=x[t_off : t_off + n].tolist(),
        solve_time_s=elapsed,
    )


def _coordinated_comparable(scenario: Scenario, coordinated: RunResult) -> bool:
    """Whether the coordinated run did the same work the LP must do.

    True when every energy device delivered ``target_kwh`` (within 1e-6 kWh) before
    its ``deadline_min`` and the room never exceeded ``comfort_c``. Reads the run's
    series only; schedules nothing.
    """
    if coordinated.temp_violation_min > 0:
        return False
    for d in scenario.devices:
        if d.kind is DeviceKind.AIR_CONDITIONER or d.target_kwh is None:
            continue
        series = coordinated.per_device_kw[d.id]
        delivered_kwh = sum(series[: d.deadline_min]) / 60.0
        if delivered_kwh < d.target_kwh - _FEASIBILITY_TOL:
            return False
    return True


def benchmark(scenario: Scenario, coordinated: RunResult) -> Benchmark:
    """Compare ``coordinated`` (from ``engine.run_coordinated(scenario)``) with the LP bound.

    Returns the LP result plus the gap in kW and %, whether the power limit is
    achievable with perfect foresight, and whether the coordinated run is a
    like-for-like comparison. Gap fields are ``None`` when the LP is not optimal.
    """
    opt = solve(scenario)
    gap_kw = gap_pct = limit_achievable = None
    if opt.peak_kw is not None:
        gap_kw = coordinated.peak_kw - opt.peak_kw
        gap_pct = 100.0 * gap_kw / coordinated.peak_kw if coordinated.peak_kw > 0 else 0.0
        limit_achievable = opt.peak_kw <= scenario.power_limit_kw + _FEASIBILITY_TOL
    return Benchmark(
        optimal=opt,
        coordinated_peak_kw=coordinated.peak_kw,
        power_limit_kw=scenario.power_limit_kw,
        gap_kw=gap_kw,
        gap_pct=gap_pct,
        limit_achievable=limit_achievable,
        coordinated_comparable=_coordinated_comparable(scenario, coordinated),
    )
