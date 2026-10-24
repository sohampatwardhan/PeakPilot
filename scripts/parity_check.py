#!/usr/bin/env python3
"""Check that the Rust engine reproduces the Python engine exactly.

Runs every named scenario through both engines, plus seeded random overrides of each
scenario's power limit and EV / water-heater energy and deadlines, and compares the full
JSON output (every per-minute value, every metric, every decision-log line). Any
difference fails the check.

Usage:
    python scripts/parity_check.py --bin rust/peakpilot-core/target/release/peakpilot

Exit code 0 = identical on every case, 1 = at least one mismatch.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from peakpilot import engine, scenarios  # noqa: E402

# Scenario knobs per CLI slug. Mirrors rust/peakpilot-core/src/scenarios.rs; the check
# below confirms each entry rebuilds the same scenario as the named Python builder.
NAMED = {
    "hot_evening": (
        scenarios.hot_evening,
        {"name": "Hot evening (14 kW limit)", "power_limit_kw": 14.0},
    ),
    "tight_limit": (
        scenarios.tight_limit,
        {"name": "Tight limit (11 kW)", "power_limit_kw": 11.0},
    ),
    "ev_offline": (
        scenarios.ev_offline,
        {"name": "EV charger offline 18:00–18:45", "power_limit_kw": 14.0, "ev_offline": (120, 165)},
    ),
    "infeasible": (
        scenarios.infeasible,
        {
            "name": "Infeasible (8 kW, early EV deadline)",
            "power_limit_kw": 8.0,
            "peak_outdoor_c": 34.0,
            "ev_kwh": 40.0,
            "ev_deadline_min": 420,
        },
    ),
    "sunny_evening": (
        scenarios.sunny_evening,
        {"name": "Sunny evening + rooftop PV (11 kW)", "power_limit_kw": 11.0, "solar": True},
    ),
}

FLAGS = {
    "power_limit_kw": "--limit",
    "ev_kwh": "--ev-kwh",
    "ev_deadline_min": "--ev-deadline-min",
    "wh_kwh": "--wh-kwh",
    "wh_deadline_min": "--wh-deadline-min",
}


def first_difference(a: object, b: object, path: str = "$") -> str | None:
    """Return the JSON path of the first difference between two values, or None."""
    if type(a) is not type(b):
        return f"{path}: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        if list(a) != list(b):
            return f"{path}: keys {list(a)} vs {list(b)}"
        for k in a:
            found = first_difference(a[k], b[k], f"{path}.{k}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            found = first_difference(x, y, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if a == b else f"{path}: {a!r} vs {b!r}"


def run_rust(binary: str, slug: str, overrides: dict) -> dict:
    cmd = [binary, "run", "--scenario", slug]
    for key, value in overrides.items():
        cmd += [FLAGS[key], repr(value)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def random_overrides(rng: random.Random) -> dict:
    return {
        "power_limit_kw": round(rng.uniform(8.0, 20.0), 2),
        "ev_kwh": round(rng.uniform(5.0, 60.0), 1),
        "ev_deadline_min": rng.randint(60, 960),
        "wh_kwh": round(rng.uniform(2.0, 20.0), 1),
        "wh_deadline_min": rng.randint(60, 960),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bin", required=True, help="path to the Rust `peakpilot` binary")
    parser.add_argument("--random-cases", type=int, default=25, help="random overrides per scenario")
    parser.add_argument("--seed", type=int, default=20261024)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    cases = failures = 0
    for slug, (builder, knobs) in NAMED.items():
        # Guard against this table drifting from the Python scenario definitions.
        mirrored = engine.compare(scenarios.custom_scenario(**knobs)).to_json_dict()
        if first_difference(engine.compare(builder()).to_json_dict(), mirrored):
            print(f"FAIL {slug}: NAMED table no longer matches scenarios.{builder.__name__}()")
            failures += 1

        for overrides in [{}] + [random_overrides(rng) for _ in range(args.random_cases)]:
            cases += 1
            expected = engine.compare(scenarios.custom_scenario(**{**knobs, **overrides})).to_json_dict()
            diff = first_difference(expected, run_rust(args.bin, slug, overrides))
            if diff:
                failures += 1
                print(f"FAIL {slug} {overrides}: {diff}")

    print(f"parity: {cases - failures}/{cases} cases identical")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
