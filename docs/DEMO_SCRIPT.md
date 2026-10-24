# PeakPilot — demo script (target 2:30, hard cap 3:00)

Spoken script for the submission video. Times are cumulative, at about 150 spoken words
per minute. Keep device data framed as SIMULATED; keep MassGIS framed as public fact.
Every number below was checked against `main` (Hot evening unless noted).

---

**[0:00–0:22] The problem**

"Clean power still has to show up at the peak. When an EV charger, a water heater and an
air conditioner all run at once on a hot evening, a building spikes the grid right when
it's most strained. PeakPilot asks: which load can wait, and for how long, while still
getting everything done?"

**[0:22–0:38] The setup**

"On the left I pick a scenario and set the building's power limit, plus how much energy
the EV and water heater need and by when. All device data is simulated and labeled. Hot
evening, 14-kilowatt limit."

**[0:38–1:08] The headline result**

"The same evening, run twice. In red, uncoordinated: the building peaks at 19 kilowatts
and sits over the limit for three hours. In green, PeakPilot holds 14 kilowatts — a 26%
lower peak, zero minutes over, every deadline met. The EV and water heater get exactly
the same energy in both runs; the peak dropped because work moved into the night, not
because anything was skipped."

**[1:08–1:22] Why, in plain language**

"Every decision is logged: the EV throttled to fit the limit, the water heater paused to
hold the building under it. And the room never crosses the 25-degree comfort limit."

**[1:22–1:52] How close to optimal?**

"How good is that? A linear program with perfect foresight of the whole evening puts a
lower bound on the peak: about 6 kilowatts. The lowest limit PeakPilot itself can hold is 7.8 —
so perfect foresight would buy 1.8 kilowatts. Could a forecast get it? Here, a forecast
just 2 degrees too cool breaks the comfort limit for nearly eight hours. That's why
PeakPilot's control stays reactive and explainable."

**[1:52–2:10] Honesty: offline + infeasible**

"When the EV charger drops offline, PeakPilot can't command it, so it reserves its last
power and says so. And this 8-kilowatt scenario is honestly infeasible: PeakPilot reports
the minutes over the limit instead of hiding them."

**[2:10–2:28] Massachusetts context + close**

"Pick a town to see its electric utility and landfill renewable projects from MassGIS —
public facts, kept separate from the simulation. PeakPilot makes the tradeoffs of a
reliable clean grid visible, honestly. Thanks."

---

## Click sequence (rehearse this)

1. Scenario = **Hot evening (14 kW)**. Point at the metric cards, then the demand chart.
2. Scroll to the decision log (AC on/off rows are hidden by default), then the room-temperature chart.
3. Scroll to **How close to optimal?** Point at Reactive floor 7.8, Lower bound 6.03, Headroom 1.77.
   Open **What if the forecast is wrong?** and set **Outdoor forecast error** to **−2.0**:
   the warning reads 462 minutes above comfort.
4. Switch scenario to **EV offline 18:00–18:45**. Point at the OFFLINE device row and the log.
5. Switch to **Infeasible (8 kW, early EV deadline)**. Point at the honesty banner.
6. Change **Town** to one with projects (e.g. Carver or Barnstable). Show the MassGIS panel.

Tip: reset the forecast slider to 0.0 after step 3, or use **↺ Reset to scenario defaults**.
