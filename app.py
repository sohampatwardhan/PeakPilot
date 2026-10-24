"""PeakPilot — Streamlit dashboard.

A thin view over ``peakpilot.engine``. It never reimplements control logic: it
builds a :class:`~peakpilot.engine.Scenario` from the sidebar, calls
``engine.compare()``, and renders the result. All device telemetry shown here is
SIMULATED and labeled as such; MassGIS panels show public facts with source +
snapshot date and are kept visually separate from the simulation.

Run with: ``streamlit run app.py``
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from peakpilot import engine, massgis, scenarios

st.set_page_config(page_title="PeakPilot", page_icon="⚡", layout="wide")


# --- Helpers ----------------------------------------------------------------


def _clock_series(result: engine.RunResult) -> list[str]:
    return [engine.clock(m) for m in result.minutes]


def _demand_figure(cmp: engine.CompareResult) -> go.Figure:
    """Baseline vs coordinated total demand, with the power-limit line."""
    x = _clock_series(cmp.baseline)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x, y=cmp.baseline.total_kw, name="Uncoordinated",
            line=dict(color="#d9534f", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=cmp.coordinated.total_kw, name="PeakPilot coordinated",
            line=dict(color="#2e8b57", width=2),
        )
    )
    fig.add_hline(
        y=cmp.power_limit_kw, line_dash="dash", line_color="#444",
        annotation_text=f"Power limit {cmp.power_limit_kw:.0f} kW",
        annotation_position="top left",
    )
    fig.update_layout(
        height=360, margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Time (16:00 → 08:00, SIMULATED)", yaxis_title="Total demand (kW)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(nticks=12),
    )
    return fig


def _temp_figure(cmp: engine.CompareResult) -> go.Figure:
    """Room temperature under both runs, with the comfort limit line."""
    x = _clock_series(cmp.baseline)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x, y=cmp.baseline.room_c, name="Uncoordinated room °C",
            line=dict(color="#d9534f", width=1.5, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=cmp.coordinated.room_c, name="Coordinated room °C",
            line=dict(color="#2e8b57", width=1.5),
        )
    )
    fig.add_hline(
        y=cmp.comfort_c, line_dash="dash", line_color="#444",
        annotation_text=f"Comfort limit {cmp.comfort_c:.0f} °C",
        annotation_position="top left",
    )
    fig.update_layout(
        height=280, margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Time (SIMULATED)", yaxis_title="Room temperature (°C)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(nticks=12),
    )
    return fig


def _device_status_rows(cmp: engine.CompareResult, scenario) -> pd.DataFrame:
    """Per-device status at the end of the coordinated run (SIMULATED)."""
    rows = []
    last_min = scenario_last_minute = engine.WINDOW_MINUTES - 1
    for spec in scenario.devices:
        series = cmp.coordinated.per_device_kw[spec.id]
        online = spec.is_online_at(last_min)
        # Find the most recent minute the device was online (its last update).
        last_update = last_min
        while last_update > 0 and not spec.is_online_at(last_update):
            last_update -= 1
        rows.append(
            {
                "Device": spec.id,
                "Kind": spec.kind.value,
                "Power kW (end)": round(series[last_min], 2),
                "Status": "online" if online else "OFFLINE / stale",
                "Last update": engine.clock(last_update),
                "Commands": ", ".join(spec.commands),
            }
        )
    return pd.DataFrame(rows)


# --- Sidebar (inputs) -------------------------------------------------------

st.sidebar.title("⚡ PeakPilot")
st.sidebar.caption("Building demand coordination — all device data SIMULATED")

scenario_names = list(scenarios.scenarios().keys())
chosen = st.sidebar.selectbox("Scenario", scenario_names, index=0)

if st.sidebar.button("↺ Reset to scenario defaults"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# Build the chosen scenario, then let the user override key knobs.
base_scenario = scenarios.scenarios()[chosen]()

st.sidebar.subheader("Building power limit")
power_limit = st.sidebar.slider(
    "Limit (kW)", min_value=8.0, max_value=20.0,
    value=float(base_scenario.power_limit_kw), step=0.5,
)

st.sidebar.subheader("EV charger (SIMULATED)")
ev_spec = next(d for d in base_scenario.devices if d.kind is engine.DeviceKind.EV)
ev_kwh = st.sidebar.slider("EV energy needed (kWh)", 5.0, 60.0, float(ev_spec.target_kwh), 1.0)
ev_deadline_h = st.sidebar.slider("EV deadline (hour)", 17, 32, 16 + ev_spec.deadline_min // 60)

st.sidebar.subheader("Water heater (SIMULATED)")
wh_spec = next(d for d in base_scenario.devices if d.kind is engine.DeviceKind.WATER_HEATER)
wh_kwh = st.sidebar.slider("Water-heater energy (kWh)", 2.0, 20.0, float(wh_spec.target_kwh), 1.0)
wh_deadline_h = st.sidebar.slider("Water-heater deadline (hour)", 17, 32, 16 + wh_spec.deadline_min // 60)

st.sidebar.subheader("Massachusetts context")
town = st.sidebar.selectbox("Town (MassGIS)", massgis.towns(), index=massgis.towns().index("Boston") if "Boston" in massgis.towns() else 0)

# Reconstruct a scenario from the (possibly overridden) inputs, preserving the
# chosen scenario's environment and any offline window.
ev_offline = ev_spec.offline_window
scenario = scenarios.custom_scenario(
    name=chosen,
    power_limit_kw=power_limit,
    ev_kwh=ev_kwh,
    ev_deadline_min=(ev_deadline_h - 16) * 60,
    wh_kwh=wh_kwh,
    wh_deadline_min=(wh_deadline_h - 16) * 60,
    ev_offline=ev_offline,
    note=base_scenario.note,
)

cmp = engine.compare(scenario)
b, co = cmp.baseline, cmp.coordinated


# --- Main -------------------------------------------------------------------

st.title("PeakPilot")
st.markdown(
    "**A more reliable clean energy system — clean power still has to show up at the peak.** "
    "Run the same evening twice and see what coordination changes. "
    ":red[All device readings and room temperature below are **SIMULATED**.]"
)
if scenario.note:
    st.info(scenario.note)

# Metric cards.
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Coordinated peak", f"{co.peak_kw:.1f}", f"-{cmp.peak_reduction_pct:.0f}% vs base", delta_color="inverse", help="Peak building demand in kW under PeakPilot")
c2.metric("Baseline peak", f"{b.peak_kw:.1f}", help="Peak demand in kW with no coordination")
c3.metric("Energy (kWh)", f"{co.total_kwh:.0f}", f"{co.total_kwh - b.total_kwh:+.1f}", help="Total energy delivered; should match the baseline (same work)")
c4.metric("Min over limit", f"{co.minutes_over_limit}", f"{co.minutes_over_limit - b.minutes_over_limit:+d}", delta_color="inverse", help="Minutes the coordinated run exceeds the power limit")
tasks_label = "✓ all" if co.all_tasks_met() else "✗ unmet"
c5.metric("Deadlines", tasks_label, help="Whether every energy task met its deadline")

# Honest-infeasibility banner.
if co.minutes_over_limit > 0 or co.temp_violation_min > 0 or not co.all_tasks_met():
    msgs = []
    if co.minutes_over_limit > 0:
        msgs.append(f"{co.minutes_over_limit} min over the power limit")
    if co.temp_violation_min > 0:
        msgs.append(f"{co.temp_violation_min} min above the comfort limit")
    unmet = {k: v for k, v in co.unmet_kwh.items() if v > 1e-6}
    if unmet:
        msgs.append("unmet energy: " + ", ".join(f"{k} {v:.1f} kWh" for k, v in unmet.items()))
    st.warning(
        "**Honest infeasibility:** this scenario cannot satisfy every constraint. "
        + "; ".join(msgs)
        + ". PeakPilot reports this rather than hiding it."
    )

# Charts.
st.subheader("Demand: uncoordinated vs coordinated (SIMULATED)")
st.plotly_chart(_demand_figure(cmp), use_container_width=True)

st.subheader("Room temperature (SIMULATED, illustrative thermal model)")
st.plotly_chart(_temp_figure(cmp), use_container_width=True)

# Decision log + device status.
left, right = st.columns([3, 2])
with left:
    st.subheader("Decision log (coordinated)")
    st.caption("Plain-language reason for each control change. SIMULATED.")
    log_rows = [d.as_row() for d in co.decision_log]
    if log_rows:
        st.dataframe(pd.DataFrame(log_rows), height=300, use_container_width=True, hide_index=True)
    else:
        st.write("No state changes logged.")

with right:
    st.subheader("Device status (SIMULATED)")
    st.dataframe(_device_status_rows(cmp, scenario), use_container_width=True, hide_index=True)

    # Per-device delivered energy.
    st.caption("Energy delivered per device (SIMULATED)")
    dev_kwh = pd.DataFrame(
        [{"Device": k, "Delivered kWh": round(v, 2), "Met": co.tasks_met.get(k, "—")}
         for k, v in co.per_device_kwh.items()]
    )
    st.dataframe(dev_kwh, use_container_width=True, hide_index=True)

# MassGIS context — kept visually separate, clearly labeled as public fact.
st.divider()
st.subheader(f"Massachusetts context — {town}")
st.caption(
    f"Public infrastructure facts (not simulation). Source: {massgis.SOURCE}. "
    f"Portal snapshot {massgis.PORTAL_SNAPSHOT_DATE}, retrieved {massgis.RETRIEVED_DATE}."
)
mc1, mc2 = st.columns([1, 2])
with mc1:
    util = massgis.utility_for(town)
    st.markdown("**Electric utility**")
    st.write(util or "—")
with mc2:
    st.markdown("**Listed landfill renewable projects**")
    projects = massgis.landfills_for(town)
    if projects:
        st.dataframe(
            pd.DataFrame(
                [{"Site": p.site, "Type": p.type, "MW (reported capacity)": p.mw,
                  "Status": p.status, "Since": p.since or "—"} for p in projects]
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.write("No listed landfill renewable projects for this town.")
st.caption(
    "⚠️ Reported MW is permitted/operating capacity, **not** generation. This data does "
    "not establish grid demand, available capacity, price, carbon intensity, or which "
    "generator supplies a building."
)
