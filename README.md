# PeakPilot

**A Massachusetts-aware building energy simulator that demonstrates IoT demand coordination — and makes the tradeoffs visible.**

PeakPilot is an IoT energy coordinator that cuts a building's peak electricity demand without cutting what gets done. Simulated smart devices (an EV charger, a water heater, and an air conditioner) report live power and room temperature. A deadline-aware controller decides which loads can wait and which can't, keeping the building under a power limit while still charging the car, heating the water, and keeping the room comfortable.

A dashboard runs the same evening twice — once without coordination, once with PeakPilot — and compares peak demand, energy delivered, deadlines met, and comfort, with a plain-language log of every decision. It handles devices going offline and flags when a limit can't be met instead of hiding it.

## The problem

When several devices switch on together, they create a large demand peak. The peak, not total energy, is what strains the grid and drives demand charges. Some loads — a battery charger, a water heater — can wait briefly. PeakPilot answers one question:

> Which device can we delay, for how long, while still getting everything done?

This is the **C3 challenge** from the Hackachusetts 2026 Energy & climate tech track: *a more reliable clean energy system — clean power still has to show up at the peak.*

## How it works

1. **Measure** — Each simulated device reports power draw and (for the room) temperature, with an ID and timestamp.
2. **Decide** — A deterministic controller checks the building power limit, device deadlines, and the room temperature constraint.
3. **Act** — It throttles or defers flexible loads to stay under the limit.
4. **Explain** — The dashboard logs a reason for each action, e.g. `17:30 ev-1: throttled to fit power limit`.

### Devices modeled

| Device | Constraint | Controller action |
|---|---|---|
| EV charger | Deliver a target energy (kWh) before a departure deadline | Throttle or pause charging |
| Water heater | Finish a heating task (kWh) before a deadline | Delay its start; respect a minimum run time |
| Air conditioner | Keep the simulated room below a comfort limit (°C) | Prioritize cooling when the room warms |

All device readings and thermal behavior are clearly labeled **SIMULATED**.

## Scheduling approach

The controller uses **least-slack-first** scheduling. Each task's slack is the time until its deadline minus the time it needs at full power. The task with the least slack gets power first. If a task runs out of slack, it runs at full power even if that breaks the limit, and the log records it.

Design principles:

- **Honest infeasibility.** When a limit cannot be met (for example, the AC must run to keep the room comfortable), the controller reports the minutes over the limit instead of hiding them.
- **Equipment-realistic behavior.** The water heater and air conditioner honor minimum run times so relays don't cycle every minute.
- **IoT failure handling.** When a device goes offline, the controller can't command it, assumes it holds its last power level, reserves that headroom, and defers other loads until it reconnects. A stale reading visibly changes the device's status.
- **Same work, lower peak.** Both runs deliver the same total energy, so peak reduction never comes from skipping work. A lower peak achieved by leaving tasks unfinished counts as a failure, not a win.

## Massachusetts context

PeakPilot adds a local planning layer from MassGIS (via the Hackachusetts climate portal). The user journey: **select a town → see its electricity context → simulate a building → compare coordinated vs. uncoordinated demand.**

| Dataset | Role | Limit |
|---|---|---|
| [Electric utility by town](https://hackachusetts2026.vercel.app/kits/utilities.zip) | Name the utility that serves the selected town | No tariffs, live demand, or grid capacity |
| [Renewables at Massachusetts landfills](https://hackachusetts2026.vercel.app/kits/landfills.zip) | Show listed renewable projects in that town (status, reported capacity) | Reported capacity is not actual generation available to the building |

The relationship is kept honest: **MassGIS describes the local infrastructure; the simulation tests building-level demand coordination.** Source links and the dataset snapshot date (tables saved 2026-10-18) are shown in the app.

## What the demo shows

Run the same scenario twice and compare:

| Metric | What it demonstrates |
|---|---|
| Peak power (kW) | Whether coordination reduced simultaneous demand |
| Peak reduction (%) | Size of the improvement |
| Energy delivered (kWh) | Whether both runs completed equivalent work |
| Tasks met | Whether deadlines were honored |
| Minutes over limit | Whether, and how honestly, the limit held |

Three scenarios make it compelling:

- **Demand spike** — the controller postpones the flexible load.
- **Room warms** — the air conditioner gets priority.
- **Device offline** — local control continues and the dashboard marks readings as stale.

## Scope

This prototype deliberately includes:

- One building, three devices, one deterministic scheduling rule
- Two bundled MassGIS datasets for local context
- A before-and-after comparison with a decision log

And deliberately excludes:

- Authentication, custom electronics, and live utility integrations
- Machine-learning control (the scheduler is rules-based and explainable)
- Carbon or cost savings claims (reducing peak demand does not by itself reduce total energy or emissions)

## Data sources and attribution

- Challenge and datasets: [Hackachusetts 2026 — Energy & climate tech](https://hackachusetts2026.vercel.app/#/climate)
- Electric utility by town and Renewables at Massachusetts landfills: MassGIS, Commonwealth of Massachusetts (confirm layer terms). Tables snapshot 2026-10-18.

All device telemetry and thermal behavior in PeakPilot is **simulated** and labeled as such.
