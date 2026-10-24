# PeakPilot — demo script (target 2:42, hard cap 3:00)

Spoken script for the submission video: six intro slides, the live dashboard, then the
closing slide. Times are cumulative, at about 150 spoken words per minute, with a few
seconds left for clicks. Keep device data framed as SIMULATED; keep MassGIS framed as
public fact. Every number below was checked against `main` (Hot evening unless noted).

The deck is `docs/PeakPilot_deck.pptx`. Slides 1–7 play in the slideshow; slides 8–14 are
hidden backup (detailed results the live demo already shows).

| Part | Time | What it covers |
| --- | --- | --- |
| Intro slides 1–6 | 0:00–1:09 | Problem, approach, who benefits, how Kiro was used |
| Live demo | 1:11–2:31 | The project working: result, log, optimality, honesty, MassGIS |
| Closing slide 7 | 2:33–2:42 | Limits, repo, thanks |

---

## Part 1 — Intro slides

**[0:00–0:10] Slide 1 · Title**

"I'm Soham, and this is PeakPilot, for Climate Tech challenge C3. It cuts a building's
peak demand without cutting the work it has to do."

**[0:10–0:22] Slide 2 · The peak**

"Clean power still has to show up at the peak. On a hot evening the EV charger, water
heater and AC all switch on together, and the building spikes."

**[0:22–0:30] Slide 3 · Which load can wait**

"Some of those loads can wait, but each has a deadline. PeakPilot asks which one can
wait, and for how long."

**[0:30–0:38] Slide 4 · Measure, decide, act, explain**

"Every minute it measures each device, decides with a deterministic least-slack-first
rule, acts, and logs why in plain language."

**[0:38–0:49] Slide 5 · Who benefits**

"That could let building owners add EV chargers and other flexible loads under the limit
they already have, and give the grid load that moves out of the peak."

**[0:49–1:09] Slide 6 · How Kiro built it**

This slide carries the Kiro judging criterion, so it gets 20 seconds. Name each card
heading as you say it.

"It was built spec-first in Kiro. Specs split each feature into requirements, design and
tasks. Steering docs hold the honesty rules. Agent hooks guard commands and check
diagrams. Through MCP, Kiro tested the live app in a browser. And property tests found
two real bugs."

*Cut to the running dashboard (about 2 s).*

---

## Part 2 — Live demo

### What to demonstrate

The rules require footage of the project working, so this part carries the video. Show
each item below once, in this order. Each one backs a judging criterion.

1. **The dashboard running, with SIMULATED labels.** Shows the working project and
   the honesty rules. (Quality and design)
2. **Same evening, run twice.** The headline: 19.0 → 14.0 kW peak, 180 → 0 minutes
   over the limit, 2/2 deadlines met, and the same EV and water-heater energy in both
   runs. (Potential value)
3. **The decision log and the room temperature.** Every action has a plain-language
   reason, and the room stays at or below 25 °C. (Quality and design)
4. **How close to optimal, and the cost of a wrong forecast.** LP lower bound 6.03 kW,
   reactive floor 7.8 kW, and a forecast 2 °C too cool means 462 minutes above comfort.
   (Implementation depth)
5. **Honesty under failure.** The offline EV charger is shown as OFFLINE, and the
   infeasible 8 kW case raises a warning banner instead of hiding the minutes over the
   limit. (Rules: report infeasibility)
6. **Massachusetts context.** A town's utility and landfill renewable projects from
   MassGIS, with source and date, kept apart from the simulation. (Unique public
   dataset)
7. *(Optional, about +12 s)* **Sunny evening + rooftop PV.** Simulated PV with MPPT
   lowers net grid import: 17.2 → 11.0 kW, 0 minutes over the 11 kW limit. This brings the
   total to about 2:54, so skip it if your cut runs long.

### Narration

**[1:11–1:20] Setup**

"Here's the live dashboard. All device data is simulated and labeled. Hot evening,
14-kilowatt limit."

**[1:20–1:36] The headline result**

"Same evening, run twice. Uncoordinated, in red, it peaks at 19 kilowatts and sits over
the limit for three hours. PeakPilot, in green, holds 14: a 26% lower peak, zero minutes
over, every deadline met, and the EV and water heater get exactly the same energy."

**[1:36–1:43] Why, in plain language**

"Every decision is logged, and the room stays under 25 degrees."

**[1:43–2:03] How close to optimal?**

"How good is that? A perfect-foresight linear program puts the lowest possible peak at
about 6 kilowatts; PeakPilot can hold 7.8. But a forecast just 2 degrees too cool breaks
comfort for nearly eight hours, so control stays reactive."

**[2:03–2:20] Honesty: offline + infeasible**

"If the EV charger drops offline, PeakPilot reserves its last power and says so. And
this 8-kilowatt case is impossible: it reports the minutes over the limit instead of
hiding them."

**[2:20–2:31] Massachusetts context**

"Pick a town to see its utility and landfill renewable projects from MassGIS, public
facts kept apart from the simulation."

*Optional PV segment, insert here:* "With simulated rooftop solar tracking its maximum
power point, the same building holds an 11-kilowatt limit."

*Cut back to the deck, slide 7 (about 2 s).*

---

## Part 3 — Closing slide

**[2:33–2:42] Slide 7 · Honest limits, and what's next**

"Everything simulated is labeled, and no cost or carbon savings are claimed. The code,
specs, steering and hooks are on GitHub. Thanks."

---

## Click sequence (rehearse this)

Before recording: start `streamlit run app.py`, open the deck, and start the slideshow
from slide 1. Hidden slides 8–14 are skipped automatically.

1. Slides 1–6, then switch to the browser.
2. Scenario = **Hot evening (14 kW)**. Point at the metric cards, then the demand chart.
3. Scroll to the decision log (AC on/off rows are hidden by default), then the
   room-temperature chart.
4. Scroll to **How close to optimal?** Point at Reactive floor 7.8, Lower bound 6.03,
   Headroom 1.77. Open **What if the forecast is wrong?** and set **Outdoor forecast
   error** to **−2.0**: the warning reads 462 minutes above comfort.
5. Use **↺ Reset to scenario defaults**, then switch scenario to **EV offline
   18:00–18:45**. Point at the OFFLINE device row and the log.
6. Switch to **Infeasible (8 kW, early EV deadline)**. Point at the honesty banner.
7. Change **Town** to one with projects (e.g. Carver or Barnstable). Show the MassGIS panel.
8. *(Optional)* Switch to **Sunny evening + rooftop PV (11 kW)**. Point at the PV line on
   the chart and the Rooftop PV metrics.
9. Switch back to the slideshow and advance to slide 7.

Tips: record the slides and the dashboard as separate takes and join them if a live switch
is awkward. Check the final cut is under 3:00 before uploading; judges stop at three minutes.
