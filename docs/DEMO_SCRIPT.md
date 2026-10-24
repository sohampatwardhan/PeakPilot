# PeakPilot — demo script (target 2:30, hard cap 3:00)

Spoken script for the submission video. Times are cumulative. Keep device data
framed as SIMULATED; keep MassGIS framed as public fact.

---

**[0:00–0:20] The problem**

"Clean power still has to show up at the peak. When an EV charger, a water heater,
and an air conditioner all run at once on a hot evening, a building spikes the grid
right when it's most strained. PeakPilot asks one question: which load can wait, and
for how long, while still getting everything done?"

**[0:20–0:45] The setup**

"This is PeakPilot. On the left I pick a scenario and set the building's power limit,
plus how much energy the EV and water heater need and by when. Everything you see for
the devices is a simulation, clearly labeled. I'll start with a hot evening and a
14-kilowatt limit."

**[0:45–1:25] The headline result**

"Here's the same evening run twice. In red, uncoordinated: everything runs at once and
the building peaks at 19 kilowatts, way over the limit, for three hours. In green,
PeakPilot: it holds the building at 14 kilowatts — a 26% lower peak — zero minutes over
the limit, and every deadline still met. Same total energy delivered in both runs. The
peak dropped because work moved into the night, not because we skipped anything."

**[1:25–1:50] The decision log + temperature**

"Every decision is explained in plain language: the EV throttled to fit the limit, the
air conditioner given priority as the room warmed. And the room never crosses the
comfort limit — the temperature chart shows the coordinated run stays under 25 degrees."

**[1:50–2:15] Honesty: offline + infeasible**

"Two things judges should see. First, when the EV charger drops offline, the controller
can't command it, so it reserves its last power and says so. Second, this scenario is
honestly infeasible: an 8-kilowatt cap with a large early EV deadline. PeakPilot doesn't
fake it — it reports the minutes over the limit instead of hiding them."

**[2:15–2:30] Massachusetts context + close**

"Finally, local context from MassGIS: pick a town, see its electric utility and listed
landfill renewable projects — public facts, kept separate from the simulation. PeakPilot
makes the tradeoffs of a reliable clean grid visible, honestly. Thanks."

---

## Click sequence (rehearse this)

1. Scenario = **Hot evening (14 kW)** — point at metric cards, then the demand chart.
2. Hover the decision log; show the room-temperature chart.
3. Switch scenario to **EV offline 18:00–18:45** — point at the OFFLINE device row + log.
4. Switch to **Infeasible (8 kW, early EV deadline)** — point at the honesty banner.
5. Change **Town** to one with projects (e.g. Carver or Barnstable) — show the MassGIS panel.
