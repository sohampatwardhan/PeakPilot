# PeakPilot — Product Steering

## What this is

PeakPilot is a Massachusetts-aware building energy simulator that demonstrates IoT demand
coordination and makes the tradeoffs visible. It is a Hackachusetts 2026 entry in the
**Energy & climate tech** track, addressing the **C3 challenge**: *a more reliable clean
energy system — clean power still has to show up at the peak.*

## Intended user

A Massachusetts building or campus facilities manager exploring how coordinating flexible
electrical loads can shave peak demand without failing to deliver required energy.

## Core value

Run the same evening twice — uncontrolled and coordinated — and show, with honest metrics,
how much peak demand coordination removes while still meeting energy requirements, deadlines,
and a room-temperature comfort constraint.

## Non-negotiable honesty rules (apply to every artifact and every line of code)

- **Simulated telemetry is always labeled SIMULATED.** Never present device readings as real.
- **MassGIS facts vs. simulation outputs are always distinguished.** Public data describes
  local infrastructure only; it never establishes live grid demand, available capacity,
  electricity price, carbon intensity, or which generator supplies a building.
- **Do not infer renewable generation from installed capacity.**
- **No cost or emissions savings claims** without supporting data inputs (we have none, so we
  make none). Reducing a peak does not by itself reduce total energy or emissions.
- **Honest infeasibility.** When a power limit cannot be met, report minutes over limit and
  unfinished tasks. A lower peak achieved by leaving work undone is a FAILURE, not a win.
- **Same work both runs.** Baseline and coordinated runs use identical workloads, initial
  conditions, and environmental inputs. Peak reduction must never come from skipping work.
- **No real equipment.** This prototype never connects to or controls real electrical hardware.

## Scope guardrails

In: one building, three devices (EV charger, water heater, air conditioner), one deterministic
scheduler, two bundled MassGIS datasets, before/after comparison, decision log, offline-device
scenario, and a perfect-foresight LP benchmark ("How close to optimal?") labeled as a lower bound
on achievable peak. Out: auth, custom electronics, live utility feeds, ML-based control, carbon/cost claims.
