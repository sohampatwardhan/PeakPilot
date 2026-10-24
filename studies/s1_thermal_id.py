"""Study S1 — learn the room thermal model from (SIMULATED) telemetry with SciPy.

Question: can a grey-box model fitted to thermostat-style data recover the engine's
RC room model, how much data and sensor noise can it tolerate, and how much better
does it predict than an untuned guess?

Data is SIMULATED: the engine's coordinated run supplies room temperature, outdoor
temperature and AC power; seeded Gaussian sensor noise is added to the room reading.
The true parameters are known, so recovery error is measurable. A real building
would supply the same three series from its thermostat and AC meter.

Model (exact for the engine, see engine._step_room_temp):
    T[t+1] = T[t] + a * (out[t] - T[t]) - b * u[t]     a = 1/(R*C), b = eta/C

Methods
    EE  equation error: ordinary least squares on one-step differences
        (scipy.linalg.lstsq). Fast, but biased when the room reading is noisy.
    OE  output error: simulate the whole trajectory and fit a, b, T0 with
        scipy.optimize.least_squares. Slower, robust to measurement noise.

Run: python studies/s1_thermal_id.py
Writes results/s1_thermal_id.json and results/s1_telemetry.csv (MATLAB parity input).
"""

from __future__ import annotations

import csv
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import linalg, optimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # repo root, so `peakpilot` imports

from peakpilot import engine, optimal, scenarios  # noqa: E402

RESULTS = HERE / "results"
SEED = 20261024
NOISE_C = (0.0, 0.05, 0.1, 0.2)  # sensor noise std, °C
TRAIN_MIN = (60, 120, 240, 480, 960)  # minutes of training data from 16:00
GUESS_ERROR = 0.30  # untuned prior: a and b each off by +/-30 %


def telemetry(scenario: engine.Scenario) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Room °C, outdoor °C, AC kW per minute from the coordinated run (SIMULATED)."""
    run = engine.compare(scenario).coordinated
    ac_id = next(d.id for d in scenario.devices if d.kind is engine.DeviceKind.AIR_CONDITIONER)
    return (
        np.asarray(run.room_c),
        np.asarray(scenario.outdoor_c),
        np.asarray(run.per_device_kw[ac_id]),
    )


def simulate(a: float, b: float, t0: float, out: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Free-run the RC model from ``t0``; returns one temperature per minute."""
    temps = np.empty(len(out))
    temps[0] = t0
    for t in range(len(out) - 1):
        temps[t + 1] = temps[t] + a * (out[t] - temps[t]) - b * u[t]
    return temps


def fit_ee(meas: np.ndarray, out: np.ndarray, u: np.ndarray) -> tuple[float, float]:
    """Equation-error OLS: dT = a*(out - T) - b*u."""
    design = np.column_stack([out[:-1] - meas[:-1], -u[:-1]])
    (a, b), *_ = linalg.lstsq(design, np.diff(meas))
    return float(a), float(b)


def fit_oe(meas: np.ndarray, out: np.ndarray, u: np.ndarray, start: tuple[float, float]) -> tuple[float, float]:
    """Output-error fit of (a, b, T0), started from ``start`` (the EE estimate)."""
    res = optimize.least_squares(
        lambda x: simulate(x[0], x[1], x[2], out, u) - meas,
        x0=[start[0], start[1], meas[0]],
        bounds=([1e-4, 1e-4, 0.0], [1.0, 5.0, 60.0]),
    )
    return float(res.x[0]), float(res.x[1])


def main() -> dict:
    RESULTS.mkdir(exist_ok=True)
    train_sc = scenarios.hot_evening()  # 31 °C outdoor peak
    test_sc = scenarios.custom_scenario(name="Hotter test evening", peak_outdoor_c=34.0)
    p = train_sc.thermal
    a_true, b_true = 1 / (p.r * p.c), p.eta / p.c

    room, out, u = telemetry(train_sc)
    test_room, test_out, test_u = telemetry(test_sc)  # noise-free ground truth
    rng = np.random.default_rng(SEED)
    noise = {s: rng.normal(0.0, s, size=room.shape) if s else np.zeros_like(room) for s in NOISE_C}

    def test_rmse(a: float, b: float) -> float:
        pred = simulate(a, b, test_room[0], test_out, test_u)
        return float(np.sqrt(np.mean((pred - test_room) ** 2)))

    guesses = [(a_true * (1 + sa * GUESS_ERROR), b_true * (1 + sb * GUESS_ERROR))
               for sa in (-1, 1) for sb in (-1, 1)]
    guess_rmse = max(test_rmse(a, b) for a, b in guesses)

    rows = []
    for sigma in NOISE_C:
        meas = room + noise[sigma]
        for n in TRAIN_MIN:
            m, o, uu = meas[:n], out[:n], u[:n]
            t_start = time.perf_counter()
            ee = fit_ee(m, o, uu)
            t_ee = time.perf_counter() - t_start
            t_start = time.perf_counter()
            oe = fit_oe(m, o, uu, ee)
            t_oe = time.perf_counter() - t_start
            for name, (a, b), secs in (("EE", ee, t_ee), ("OE", oe, t_oe)):
                rows.append({
                    "noise_c": sigma, "train_min": n, "method": name,
                    "ac_on_min": int((uu > 0).sum()),
                    "a": a, "b": b,
                    "a_err_pct": 100 * (a - a_true) / a_true,
                    "b_err_pct": 100 * (b - b_true) / b_true,
                    "test_rmse_c": test_rmse(a, b),
                    "fit_s": secs,
                })

    # Downstream: how far does the perfect-foresight LP bound move when the room model
    # is the fitted one (OE, 0.2 °C noise, 240 min) or an untuned +/-30 % guess?
    oe_row = next(r for r in rows if r["method"] == "OE" and r["noise_c"] == 0.2 and r["train_min"] == 240)
    lp = {"true": optimal.solve(test_sc).peak_kw}
    for label, (a, b) in [("fitted_oe", (oe_row["a"], oe_row["b"]))] + [
        (f"guess_{i}", g) for i, g in enumerate(guesses)
    ]:
        # a = 1/(R*C), b = eta/C; hold C fixed so (a, b) map to one (R, eta).
        thermal = dataclasses.replace(p, r=1 / (a * p.c), eta=b * p.c)
        lp[label] = optimal.solve(dataclasses.replace(test_sc, thermal=thermal)).peak_kw

    # MATLAB parity input: the full 960-minute window at 0.1 °C noise.
    with (RESULTS / "s1_telemetry.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["minute", "room_meas_c", "outdoor_c", "ac_kw", "room_true_c"])
        for t in range(len(room)):
            w.writerow([t, f"{room[t] + noise[0.1][t]:.6f}", out[t], u[t], f"{room[t]:.6f}"])

    result = {
        "label": "SIMULATED telemetry; seeded sensor noise",
        "seed": SEED,
        "a_true": a_true, "b_true": b_true,
        "untuned_guess_error_pct": 100 * GUESS_ERROR,
        "untuned_guess_worst_test_rmse_c": guess_rmse,
        "lp_bound_kw_by_model": lp,
        "rows": rows,
    }
    (RESULTS / "s1_thermal_id.json").write_text(json.dumps(result, indent=2))
    return result


def _report(r: dict) -> None:
    print(f"true a={r['a_true']:.5f} b={r['b_true']:.5f}; "
          f"untuned ±30% guess worst test RMSE {r['untuned_guess_worst_test_rmse_c']:.3f} °C")
    print("LP bound kW by room model:", {k: (round(v, 3) if v is not None else None)
                                          for k, v in r["lp_bound_kw_by_model"].items()})
    print("| noise °C | train min | AC-on min | method | a err % | b err % | test RMSE °C | fit s |")
    print("|---|---|---|---|---|---|---|---|")
    for row in r["rows"]:
        print(f"| {row['noise_c']} | {row['train_min']} | {row['ac_on_min']} | {row['method']} | "
              f"{row['a_err_pct']:+.1f} | {row['b_err_pct']:+.1f} | {row['test_rmse_c']:.3f} | {row['fit_s']:.4f} |")


if __name__ == "__main__":
    _report(main())
