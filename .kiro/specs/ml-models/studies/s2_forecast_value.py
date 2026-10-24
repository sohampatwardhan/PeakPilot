"""Study S2 — what would a learned load forecast be worth? (SIMULATED)

PeakPilot's coordinated scheduler is reactive: it sees only the current minute. The
LP in ``peakpilot.optimal`` sees the whole evening. This study measures the space
between them and how much of it a *forecast* (rather than perfect foresight) keeps.

Part A — value of foresight. For "Hot evening":
    reactive floor   lowest power limit the engine holds with every deadline met,
                     0 min over and 0 min above comfort (0.1 kW sweep)
    perfect bound    LP peak with the true base load and outdoor temperature
    forecast plan    LP solved on a *wrong* base load / outdoor series, then played
                     open-loop against the truth: realized peak = max(true base +
                     planned device kW); comfort re-simulated with the true outdoor.
Part B — learned forecasts. A seeded synthetic history of evenings (base load scales
with the day's outdoor peak, jittered timing, AR(1) noise) trains three day-ahead
forecasters with SciPy; each forecast is planned and realized as in Part A.

Honesty: every series here is SIMULATED. Part B's history is synthetic, so the
relation the regression "discovers" was planted by this script. Part B shows the
pipeline and the error-to-peak sensitivity, not a real-world accuracy claim.

Run: python .kiro/specs/ml-models/studies/s2_forecast_value.py
Writes results/s2_forecast_value.json and results/s2_history.csv (MATLAB parity input).
"""

from __future__ import annotations

import csv
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
from scipy import linalg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))

from peakpilot import engine, optimal, scenarios  # noqa: E402

RESULTS = HERE / "results"
SEED = 20261024
N = engine.WINDOW_MINUTES
TRAIN_DAYS, TEST_DAYS = 90, 30
RIDGE_LAMBDA = 1.0


# --- Helpers ----------------------------------------------------------------


def feasible(run: engine.RunResult) -> bool:
    return run.minutes_over_limit == 0 and run.all_tasks_met() and run.temp_violation_min == 0


def reactive_floor(base: engine.Scenario) -> tuple[float, float]:
    """(lowest feasible limit, coordinated peak there) from a 0.1 kW sweep down from 14."""
    best = None
    for tenths in range(140, 50, -1):
        limit = tenths / 10
        run = engine.compare(dataclasses.replace(base, power_limit_kw=limit)).coordinated
        if not feasible(run):
            break
        best = (limit, run.peak_kw)
    assert best is not None
    return best


def room_series(sc: engine.Scenario, ac_kw: np.ndarray) -> np.ndarray:
    p = sc.thermal
    a, b = 1 / (p.r * p.c), p.eta / p.c
    temps = np.empty(N)
    temps[0] = p.start_c
    out = np.asarray(sc.outdoor_c)
    for t in range(N - 1):
        temps[t + 1] = temps[t] + a * (out[t] - temps[t]) - b * ac_kw[t]
    return temps


def plan_and_realize(truth: engine.Scenario, base_fc: np.ndarray, out_fc: np.ndarray | None = None) -> dict:
    """Plan with the LP on a forecast, then play the plan against ``truth``."""
    planned_sc = dataclasses.replace(
        truth,
        base_load=tuple(float(x) for x in np.maximum(base_fc, 0.0)),
        outdoor_c=truth.outdoor_c if out_fc is None else tuple(float(x) for x in out_fc),
    )
    plan = optimal.solve(planned_sc)
    if plan.status != "optimal":
        return {"status": plan.status}
    devices = np.sum([np.asarray(v) for v in plan.per_device_kw.values()], axis=0)
    ac_id = next(d.id for d in truth.devices if d.kind is engine.DeviceKind.AIR_CONDITIONER)
    room = room_series(truth, np.asarray(plan.per_device_kw[ac_id]))
    realized = np.asarray(truth.base_load) + devices
    return {
        "status": "optimal",
        "planned_peak_kw": plan.peak_kw,
        "realized_peak_kw": float(realized.max()),
        "comfort_violation_min": int((room > truth.thermal.comfort_c + 1e-9).sum()),
        "max_room_c": float(room.max()),
    }


# --- Part A -----------------------------------------------------------------


def part_a(sc: engine.Scenario) -> dict:
    base = np.asarray(sc.base_load)
    out = np.asarray(sc.outdoor_c)
    rng = np.random.default_rng(SEED)
    floor_limit, floor_peak = reactive_floor(sc)
    bound = optimal.solve(sc).peak_kw

    def shifted(x: np.ndarray, minutes: int) -> np.ndarray:
        return np.concatenate([np.full(minutes, x[0]), x[:-minutes]]) if minutes > 0 else \
            np.concatenate([x[-minutes:], np.full(-minutes, x[-1])])

    cases = {
        "perfect": (base, None),
        "base x0.9": (base * 0.9, None),
        "base x1.1": (base * 1.1, None),
        "base x1.2": (base * 1.2, None),
        "base 30 min early": (shifted(base, -30), None),
        "base 60 min early": (shifted(base, -60), None),
        "base 30 min late": (shifted(base, 30), None),
        "base 60 min late": (shifted(base, 60), None),
        "base noise 0.2 kW": (base + rng.normal(0, 0.2, N), None),
        "base noise 0.5 kW": (base + rng.normal(0, 0.5, N), None),
        "outdoor -2 °C": (base, out - 2.0),
        "outdoor +2 °C": (base, out + 2.0),
    }
    rows = []
    for name, (bfc, ofc) in cases.items():
        r = plan_and_realize(sc, bfc, ofc)
        r["case"] = name
        r["base_mae_kw"] = float(np.mean(np.abs(bfc - base)))
        rows.append(r)
    return {"reactive_floor_limit_kw": floor_limit, "reactive_floor_peak_kw": floor_peak,
            "perfect_bound_kw": bound, "cases": rows}


# --- Part B -----------------------------------------------------------------


def synthetic_history(sc: engine.Scenario, days: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """(outdoor peak °C per day, base load kW per day x minute), SIMULATED."""
    profile = np.asarray(sc.base_load)
    peaks = rng.uniform(24.0, 35.0, days)
    loads = np.empty((days, N))
    for d in range(days):
        shift = int(round(rng.normal(0, 20)))  # evening routine timing, minutes
        day = np.roll(profile, shift) * (1 + 0.04 * (peaks[d] - 30.0))
        ar = np.empty(N)
        ar[0] = 0.0
        eps = rng.normal(0, 0.05, N)
        for t in range(1, N):
            ar[t] = 0.95 * ar[t - 1] + eps[t]
        loads[d] = np.maximum(day + ar, 0.2)
    return peaks, loads


def part_b(sc: engine.Scenario) -> dict:
    rng = np.random.default_rng(SEED + 1)
    peaks, loads = synthetic_history(sc, TRAIN_DAYS + TEST_DAYS, rng)
    tr_p, tr_y, te_p, te_y = peaks[:TRAIN_DAYS], loads[:TRAIN_DAYS], peaks[TRAIN_DAYS:], loads[TRAIN_DAYS:]

    with (RESULTS / "s2_history.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "split", "outdoor_peak_c"] + [f"m{t}" for t in range(N)])
        for d in range(len(peaks)):
            w.writerow([d, "train" if d < TRAIN_DAYS else "test", f"{peaks[d]:.4f}"]
                       + [f"{x:.4f}" for x in loads[d]])

    # Ridge regression, one shared design for all 960 minutes: y[d, t] = w0[t] + w1[t] * peak[d].
    x_tr = np.column_stack([np.ones(TRAIN_DAYS), tr_p - 30.0])
    reg = RIDGE_LAMBDA * np.diag([0.0, 1.0])  # do not shrink the intercept
    weights = linalg.solve(x_tr.T @ x_tr + reg, x_tr.T @ tr_y, assume_a="pos")
    climatology = tr_y.mean(axis=0)

    models = {
        "persistence (yesterday)": lambda d: loads[TRAIN_DAYS + d - 1],
        "climatology (mean day)": lambda d: climatology,
        "ridge on outdoor peak": lambda d: np.array([1.0, te_p[d] - 30.0]) @ weights,
    }
    summary = {}
    perfect = []
    for d in range(TEST_DAYS):
        truth = dataclasses.replace(
            sc, base_load=tuple(float(x) for x in te_y[d]),
            outdoor_c=scenarios._outdoor_profile(peak_c=float(te_p[d])),
        )
        perfect.append(optimal.solve(truth).peak_kw)
        for name, fc in models.items():
            r = plan_and_realize(truth, fc(d))
            s = summary.setdefault(name, {"mae": [], "excess": [], "violation_days": 0})
            s["mae"].append(float(np.mean(np.abs(fc(d) - te_y[d]))))
            s["excess"].append(r["realized_peak_kw"] - perfect[-1])
            s["violation_days"] += int(r["comfort_violation_min"] > 0)
    return {
        "train_days": TRAIN_DAYS, "test_days": TEST_DAYS, "ridge_lambda": RIDGE_LAMBDA,
        "perfect_bound_mean_kw": float(np.mean(perfect)),
        "models": {k: {"mae_kw": float(np.mean(v["mae"])),
                       "mean_excess_peak_kw": float(np.mean(v["excess"])),
                       "p90_excess_peak_kw": float(np.percentile(v["excess"], 90)),
                       "comfort_violation_days": v["violation_days"]}
                   for k, v in summary.items()},
    }


def main() -> dict:
    RESULTS.mkdir(exist_ok=True)
    sc = scenarios.hot_evening()
    result = {"label": "SIMULATED; Part B history is synthetic", "seed": SEED,
              "scenario": sc.name, "part_a": part_a(sc), "part_b": part_b(sc)}
    (RESULTS / "s2_forecast_value.json").write_text(json.dumps(result, indent=2))
    return result


def _report(r: dict) -> None:
    a = r["part_a"]
    print(f"reactive floor: limit {a['reactive_floor_limit_kw']} kW, peak {a['reactive_floor_peak_kw']:.2f} kW; "
          f"perfect-foresight bound {a['perfect_bound_kw']:.2f} kW")
    print("| forecast case | base MAE kW | planned peak | realized peak | comfort viol. min |")
    print("|---|---|---|---|---|")
    for c in a["cases"]:
        print(f"| {c['case']} | {c['base_mae_kw']:.2f} | {c.get('planned_peak_kw', 0):.2f} | "
              f"{c.get('realized_peak_kw', 0):.2f} | {c.get('comfort_violation_min', '-')} |")
    b = r["part_b"]
    print(f"\nPart B: perfect-foresight mean bound {b['perfect_bound_mean_kw']:.2f} kW over {b['test_days']} test days")
    print("| model | MAE kW | mean excess peak kW | p90 excess kW | comfort-violation days |")
    print("|---|---|---|---|---|")
    for k, m in b["models"].items():
        print(f"| {k} | {m['mae_kw']:.3f} | {m['mean_excess_peak_kw']:.2f} | {m['p90_excess_peak_kw']:.2f} | "
              f"{m['comfort_violation_days']} |")


if __name__ == "__main__":
    _report(main())
