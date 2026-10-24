"""Study S4 — rooftop PV with MPPT: how well does the tracker track, and what is PV worth
to the peak? (SIMULATED)

Part A — the tracker. On the "Sunny evening + rooftop PV" scenario:
    sweep        perturb-and-observe tracking efficiency (tracked ÷ true-MPP DC energy)
                 across step sizes and perturbations per minute
    cross-check  the engine's golden-section MPP against SciPy's bounded scalar
                 optimizer on every sunlit minute
    clouds       the same tracker on a deterministic cloud-edge irradiance series
                 (20-minute dips to 25 %), where the operating point must chase a
                 moving maximum
Part B — value to the peak. The tight 11 kW workload with no PV and with the array
scaled ×0.5, ×1, ×1.5, ×2 (current and inverter rating together):
    uncoordinated peak, coordinated peak at 11 kW, the scheduler's reactive floor
    (``optimal.reactive_floor``) and the perfect-foresight LP bound (``optimal.solve``).
    Every case does the same EV and water-heater work; PV only changes net import.

Honesty: irradiance is an illustrative clear-sky curve (Part A's clouds are a fixed
pattern, not weather), the array is an ideal single-diode model, and every number is
SIMULATED. Nothing here claims cost or emissions savings.

Run: python studies/s4_solar_mppt.py
Writes results/s4_solar_mppt.json.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

from scipy import optimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from peakpilot import engine, optimal, scenarios  # noqa: E402

RESULTS = HERE / "results"
N = engine.WINDOW_MINUTES
STEPS_V = (0.5, 1.0, 2.0, 5.0, 10.0)
ITERATIONS = (1, 5, 20)
SCALES = (0.5, 1.0, 1.5, 2.0)


def with_array(sc: engine.Scenario, array: engine.PVArray, irradiance=None) -> engine.Scenario:
    g = sc.solar.irradiance_w_m2 if irradiance is None else irradiance
    return dataclasses.replace(sc, solar=engine.Solar(irradiance_w_m2=tuple(g), array=array))


def cloud_edges(clear: tuple[float, ...]) -> tuple[float, ...]:
    """Clear sky with a 20-minute dip to 25 % at the start of every hour (deterministic)."""
    return tuple(round(g * (0.25 if (m % 60) < 20 else 1.0), 4) for m, g in enumerate(clear))


# --- Part A -----------------------------------------------------------------


def part_a(sc: engine.Scenario) -> dict:
    base = sc.solar.array
    sweep = []
    for step in STEPS_V:
        for iters in ITERATIONS:
            arr = dataclasses.replace(base, mppt_step_v=step, mppt_iterations=iters)
            sol = engine.simulate_solar(with_array(sc, arr))
            sweep.append({"step_v": step, "iterations": iters,
                          "tracking_efficiency": sol.tracking_efficiency, "pv_kwh": sol.pv_kwh})

    # Cross-check the engine's golden-section MPP against SciPy on every sunlit minute.
    sol = engine.simulate_solar(sc)
    worst_rel = 0.0
    sunlit = 0
    for g, cell in zip(sol.irradiance_w_m2, sol.cell_c):
        if g <= 0:
            continue
        sunlit += 1
        isc, voc, a = engine._pv_curve(g, cell, base)
        golden = engine._true_mpp_w(isc, voc, a)
        res = optimize.minimize_scalar(lambda v: -engine._pv_power_w(v, isc, voc, a),
                                       bounds=(0.0, voc), method="bounded",
                                       options={"xatol": 1e-9})
        worst_rel = max(worst_rel, abs(golden - (-res.fun)) / golden)

    clouds = []
    cloudy = cloud_edges(sc.solar.irradiance_w_m2)
    for iters in ITERATIONS:
        arr = dataclasses.replace(base, mppt_iterations=iters)
        s = engine.simulate_solar(with_array(sc, arr, cloudy))
        clouds.append({"iterations": iters, "tracking_efficiency": s.tracking_efficiency,
                       "pv_kwh": s.pv_kwh})

    return {
        "default": {"step_v": base.mppt_step_v, "iterations": base.mppt_iterations,
                    "tracking_efficiency": sol.tracking_efficiency, "pv_kwh": sol.pv_kwh,
                    "peak_pv_kw": max(sol.pv_kw), "sunlit_min": sunlit},
        "sweep": sweep,
        "scipy_mpp_max_rel_diff": worst_rel,
        "clouds": clouds,
        "trace": {"mppt_v": list(sol.mppt_v), "pv_kw": list(sol.pv_kw),
                  "mpp_kw": list(sol.mpp_kw), "irradiance_w_m2": list(sol.irradiance_w_m2)},
    }


# --- Part B -----------------------------------------------------------------


def peaks(sc: engine.Scenario) -> dict:
    cmp = engine.compare(sc)
    floor = optimal.reactive_floor(sc)
    lp = optimal.solve(sc)
    return {
        "pv_kwh": cmp.solar.pv_kwh if cmp.solar else 0.0,
        "uncoordinated_peak_kw": cmp.baseline.peak_kw,
        "coordinated_peak_kw": cmp.coordinated.peak_kw,
        "coordinated_all_met": cmp.coordinated.all_tasks_met()
        and cmp.coordinated.minutes_over_limit == 0 and cmp.coordinated.temp_violation_min == 0,
        "task_kwh": sum(v for k, v in cmp.coordinated.per_device_kwh.items() if k != "ac-1"),
        "reactive_floor_kw": floor.limit_kw,
        "lp_bound_kw": lp.peak_kw,
    }


def part_b(sc: engine.Scenario) -> dict:
    rows = [{"scale": 0.0, **peaks(dataclasses.replace(sc, solar=None))}]
    base = sc.solar.array
    for scale in SCALES:
        arr = dataclasses.replace(base, isc_stc_a=base.isc_stc_a * scale,
                                  inverter_kw=base.inverter_kw * scale)
        rows.append({"scale": scale, **peaks(with_array(sc, arr))})
    return {"power_limit_kw": sc.power_limit_kw, "rows": rows}


def main() -> dict:
    sc = scenarios.sunny_evening()
    out = {
        "label": "SIMULATED; illustrative clear-sky irradiance and ideal single-diode array",
        "scenario": sc.name,
        "part_a": part_a(sc),
        "part_b": part_b(sc),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "s4_solar_mppt.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    r = main()
    a, b = r["part_a"], r["part_b"]
    d = a["default"]
    print(f"default tracker: {d['tracking_efficiency']:.5f} ({d['pv_kwh']:.2f} kWh, peak {d['peak_pv_kw']:.2f} kW)")
    for row in a["sweep"]:
        print(f"  step {row['step_v']:>4} V x{row['iterations']:>2}: {row['tracking_efficiency']:.5f}")
    print(f"golden vs SciPy MPP, max relative diff: {a['scipy_mpp_max_rel_diff']:.2e}")
    for row in a["clouds"]:
        print(f"  clouds x{row['iterations']:>2}: {row['tracking_efficiency']:.5f}")
    for row in b["rows"]:
        print(f"scale {row['scale']}: PV {row['pv_kwh']:.1f} kWh, uncoord {row['uncoordinated_peak_kw']:.2f}, "
              f"floor {row['reactive_floor_kw']}, LP {row['lp_bound_kw']:.3f}, tasks {row['task_kwh']:.2f}, "
              f"ok {row['coordinated_all_met']}")
