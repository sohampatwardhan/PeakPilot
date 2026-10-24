"""PeakPilot — Streamlit dashboard.

A thin view over ``peakpilot.engine``. It never reimplements control logic: it
builds a :class:`~peakpilot.engine.Scenario` from the sidebar, calls
``engine.compare()``, and renders the result. All device telemetry shown here is
SIMULATED and labeled as such; MassGIS panels show public facts with source +
snapshot date and are kept visually separate from the simulation.

Run with: ``streamlit run app.py``
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from peakpilot import engine, learn, massgis, optimal, scenarios

st.set_page_config(page_title="PeakPilot", page_icon="⚡", layout="wide")


# --- Helpers ----------------------------------------------------------------


@st.cache_data(hash_funcs={engine.Scenario: repr})
def _benchmark(scenario: engine.Scenario, _coordinated: engine.RunResult) -> optimal.Benchmark:
    """Cached perfect-foresight benchmark, keyed on every Scenario field.

    ``_coordinated`` is left out of the key: it is a deterministic function of the
    scenario, so the same scenario always pairs with the same coordinated run.
    """
    return optimal.benchmark(scenario, _coordinated)


@st.cache_data(hash_funcs={engine.Scenario: repr})
def _calibration(scenario: engine.Scenario) -> tuple[learn.ThermalFit | None, str]:
    """Room model fitted to SIMULATED thermostat telemetry from ``scenario``.

    Returns ``(fit, "")``, or ``(None, reason)`` when the telemetry cannot be fitted.
    """
    try:
        return learn.fit_thermal(*learn.simulated_telemetry(scenario)), ""
    except ValueError as err:
        return None, str(err)


@st.cache_data(hash_funcs={engine.Scenario: repr, learn.ForecastError: repr})
def _forecast_cost(scenario: engine.Scenario, error: learn.ForecastError) -> learn.ForecastCost:
    """Cached open-loop plan-on-a-forecast result for one scenario and forecast error."""
    return learn.forecast_cost(scenario, error)


# Forecast-error choices (spec R3.2). Explicit option lists keep every value exact.
_SCALES = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2]
_SHIFTS = [-60, -45, -30, -15, 0, 15, 30, 45, 60]
_NOISES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
_BIASES = [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


# Deadline choices as hours since midnight of the first day: 17 → 17:00, 32 → 08:00
# next morning. The window starts at 16:00, so deadline minutes = (hour - 16) * 60.
_DEADLINE_HOURS = list(range(17, 33))


def _hour_label(hour: int) -> str:
    """Clock label for a deadline hour that may run past midnight (e.g. 31 → 07:00)."""
    return f"{hour % 24:02d}:00"


# AC comfort-control toggles. They fire every few minutes on a warm evening and
# would otherwise bury the EV and water-heater decisions in the log.
_AC_CYCLING_PREFIXES = ("cooling ON", "cooling OFF")


def _is_ac_cycling(row: dict) -> bool:
    return row["message"].startswith(_AC_CYCLING_PREFIXES)


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
    value=float(base_scenario.power_limit_kw), step=0.5, format="%.1f",
)

st.sidebar.subheader("EV charger (SIMULATED)")
ev_spec = next(d for d in base_scenario.devices if d.kind is engine.DeviceKind.EV)
ev_kwh = st.sidebar.slider("EV energy needed (kWh)", 5.0, 60.0, float(ev_spec.target_kwh), 1.0, format="%.0f")
ev_deadline_h = st.sidebar.select_slider(
    "EV deadline", options=_DEADLINE_HOURS,
    value=16 + ev_spec.deadline_min // 60, format_func=_hour_label,
)

st.sidebar.subheader("Water heater (SIMULATED)")
wh_spec = next(d for d in base_scenario.devices if d.kind is engine.DeviceKind.WATER_HEATER)
wh_kwh = st.sidebar.slider("Water-heater energy (kWh)", 2.0, 20.0, float(wh_spec.target_kwh), 1.0, format="%.0f")
wh_deadline_h = st.sidebar.select_slider(
    "Water-heater deadline", options=_DEADLINE_HOURS,
    value=16 + wh_spec.deadline_min // 60, format_func=_hour_label,
)

st.sidebar.subheader("Room model")
use_calibrated = st.sidebar.toggle(
    "Use calibrated room model", value=False, key="use_calibrated",
    help="Fit the room's thermal model to SIMULATED thermostat telemetry and run both "
    "evenings on the fitted model. See \"Calibrate the room model\" below.",
)

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

# Calibration fits telemetry from the default ("true") room model; the toggle then
# swaps the fitted model in. Both runs always share the same model (same work).
calibration, calibration_error = _calibration(scenario)
if use_calibrated and calibration is not None:
    scenario = dataclasses.replace(scenario, thermal=calibration.params)
    room_model_label = (
        f"calibrated from SIMULATED telemetry (R {calibration.params.r:.3f}, "
        f"eta {calibration.params.eta:.3f})"
    )
else:
    room_model_label = "default illustrative parameters"

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
# Split energy into the deadline tasks (EV + water heater, which must match the
# baseline) and AC runtime (which legitimately differs between runs).
ac_ids = {d.id for d in scenario.devices if d.kind is engine.DeviceKind.AIR_CONDITIONER}
task_kwh_co = sum(v for k, v in co.per_device_kwh.items() if k not in ac_ids)
task_kwh_b = sum(v for k, v in b.per_device_kwh.items() if k not in ac_ids)
ac_kwh_co = sum(v for k, v in co.per_device_kwh.items() if k in ac_ids)
ac_kwh_b = sum(v for k, v in b.per_device_kwh.items() if k in ac_ids)
energy_diff = co.total_kwh - b.total_kwh
tasks_match = abs(task_kwh_co - task_kwh_b) < 0.05
if abs(energy_diff) < 0.05:
    energy_delta = "same as baseline"
elif tasks_match:
    energy_delta = f"{energy_diff:+.1f} kWh, AC runtime"
else:
    energy_delta = f"{energy_diff:+.1f} kWh vs baseline"
energy_help = (
    f"Total energy in the coordinated run. Baseline: {b.total_kwh:.1f} kWh. "
    f"EV + water heater: {task_kwh_co:.1f} kWh (baseline {task_kwh_b:.1f}). "
    f"AC: {ac_kwh_co:.1f} kWh (baseline {ac_kwh_b:.1f}). "
    "The deadline tasks should match the baseline; AC runtime can differ because "
    "coordination changes when the room is cooled."
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Coordinated peak", f"{co.peak_kw:.1f} kW", f"-{cmp.peak_reduction_pct:.0f}% vs base", delta_color="inverse", help="Peak building demand under PeakPilot")
c2.metric("Baseline peak", f"{b.peak_kw:.1f} kW", help="Peak demand with no coordination")
c3.metric("Energy delivered", f"{co.total_kwh:.0f} kWh", energy_delta, delta_color="off" if tasks_match else "normal", help=energy_help)
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
st.caption(f"Room model in use: {room_model_label}.")

# Perfect-foresight benchmark — a separate panel, not part of the comparison above.
bench = _benchmark(scenario, co)
opt = bench.optimal
with st.container(border=True):
    st.subheader("How close to optimal? (SIMULATED)")
    st.caption(
        "A linear program with **perfect foresight** of the whole evening (it knows the base "
        "load and outdoor temperature in advance) finds the lowest peak any schedule could "
        "reach while doing the same work: every energy target by its deadline, device power "
        "limits, the offline hold, and the room at or below the comfort limit."
    )
    if opt.status == "infeasible":
        st.error(
            "**No schedule meets every deadline and the comfort limit, even with perfect "
            "foresight.** No benchmark number is shown for this scenario."
        )
    elif opt.status == "error":
        st.error(f"The benchmark solver did not finish: {opt.message} No number is shown.")
    else:
        floor = bench.floor
        lo, hi, step = floor.grid_kw
        m1, m2, m3 = st.columns(3)
        m1.metric(
            "Reactive floor (kW)", "none" if floor.limit_kw is None else f"{floor.limit_kw:.1f}",
            help=f"Lowest power limit PeakPilot's scheduler holds with every deadline met, 0 minutes "
            f"over the limit and the room within comfort. Searched from {lo:.0f} to {hi:.0f} kW "
            f"in {step} kW steps.",
        )
        m2.metric(
            "Lower bound on achievable peak (kW)", f"{opt.peak_kw:.2f}",
            help="No schedule can do the same work with a lower peak. A lower bound, not a schedule a device could necessarily follow.",
        )
        if bench.headroom_kw is None:
            m3.metric("Headroom (kW)", "—", help="Needs both a reactive floor and a bound.")
        else:
            m3.metric(
                "Headroom (kW)", f"{bench.headroom_kw:.2f}",
                help=f"How much lower than the reactive floor a planner with perfect foresight could "
                f"go: {bench.headroom_pct:.0f}% of the floor.",
            )
            st.caption(
                f"Perfect foresight could hold {bench.headroom_kw:.2f} kW ({bench.headroom_pct:.0f}%) "
                f"below the lowest limit the reactive scheduler holds."
            )
        if floor.limit_kw is None:
            st.warning(
                f"No power limit from {lo:.0f} to {hi:.0f} kW lets the scheduler finish every task "
                "with 0 minutes over the limit and the room within comfort, so no floor is shown."
            )
        elif not floor.monotone:
            st.info(
                f"Not every limit above {floor.limit_kw:.1f} kW works: in this scenario, raising the "
                "limit can break feasibility again. The floor is the lowest limit that works, not a "
                "threshold above which everything does."
            )
        if not bench.limit_achievable:
            st.warning(
                f"The {bench.power_limit_kw:.1f} kW limit cannot be met even with perfect "
                f"foresight: the lowest possible peak is {opt.peak_kw:.2f} kW."
            )
        if not bench.coordinated_comparable:
            st.info(
                "The coordinated run missed a deadline or the comfort limit, so it did different "
                "work from the benchmark. This comparison is not like-for-like."
            )
        st.caption(
            f"At the {bench.power_limit_kw:.1f} kW limit you set, the coordinated run peaks at "
            f"{bench.coordinated_peak_kw:.2f} kW, {bench.gap_kw:.2f} kW above the bound. PeakPilot "
            "aims to stay under the limit you set, not to push the peak as low as possible, so "
            "the reactive floor, not that gap, is the fair comparison."
        )

        with st.expander("What if the forecast is wrong? (SIMULATED)"):
            st.caption(
                "A planner with a forecast instead of perfect foresight: the LP plans every device "
                "on a wrong base-load or outdoor forecast, and the plan is played against the true "
                "evening with no correction."
            )
            f1, f2 = st.columns(2)
            scale = f1.select_slider("Base-load forecast scale", _SCALES, value=1.0, format_func=lambda s: f"{s:.0%}")
            shift = f1.select_slider("Base-load timing error (min, + = late)", _SHIFTS, value=0)
            noise = f2.select_slider("Base-load forecast noise (kW)", _NOISES, value=0.0)
            bias = f2.select_slider("Outdoor forecast error (°C, − = too cool)", _BIASES, value=0.0)
            cost = _forecast_cost(scenario, learn.ForecastError(scale, shift, noise, bias))
            if cost.status != "optimal":
                st.info("No plan exists on this forecast (the planning LP is infeasible).")
            else:
                n1, n2, n3 = st.columns(3)
                n1.metric("Planned peak (kW)", f"{cost.planned_peak_kw:.2f}", help="What the plan expects on the forecast")
                n2.metric(
                    "Realized peak (kW)", f"{cost.realized_peak_kw:.2f}",
                    help=f"True base load plus the planned device power; "
                    f"{cost.realized_peak_kw - opt.peak_kw:+.2f} kW vs the perfect-foresight bound",
                )
                n3.metric("Min above comfort", f"{cost.comfort_violation_min}", help="Planned AC against the true outdoor temperature")
                if cost.comfort_violation_min > 0:
                    st.warning(
                        f"This plan breaks the comfort limit for {cost.comfort_violation_min} minutes: "
                        "a too-cool outdoor forecast under-plans cooling."
                    )
                elif floor.limit_kw is not None and cost.realized_peak_kw >= floor.limit_kw - 1e-6:
                    st.warning(
                        f"No better than reacting: the realized peak is at or above the "
                        f"{floor.limit_kw:.1f} kW reactive floor."
                    )
                elif floor.limit_kw is not None:
                    st.success(
                        f"{floor.limit_kw - cost.realized_peak_kw:.2f} kW below the reactive floor "
                        "with this forecast error."
                    )
            st.caption(
                "Open-loop and SIMULATED. PeakPilot's control stays the reactive scheduler; this "
                "shows what a forecast would have to be worth before planning could replace it."
            )

    with st.expander("Calibrate the room model (SIMULATED telemetry)"):
        st.caption(
            "Fits the room's thermal model to thermostat-style telemetry: the coordinated run's "
            "room temperature with seeded 0.2 °C sensor noise, the outdoor temperature, and AC "
            "power. A real building would supply measured telemetry instead. Output-error least "
            "squares (SciPy), seeded by ordinary least squares."
        )
        if calibration is None:
            st.warning(f"This telemetry cannot be fitted: {calibration_error}.")
        else:
            true = scenarios.custom_scenario().thermal
            fitted = calibration.params
            st.dataframe(
                pd.DataFrame([
                    {"Param": "R", "Default": true.r, "Fitted": round(fitted.r, 3)},
                    {"Param": "eta", "Default": true.eta, "Fitted": round(fitted.eta, 3)},
                    {"Param": "C (fixed)", "Default": true.c, "Fitted": fitted.c},
                ]).assign(**{"Error %": lambda d: (100 * (d["Fitted"] / d["Default"] - 1)).round(1)}),
                use_container_width=True, hide_index=True,
            )
            st.caption(
                f"R in °C per kW, eta cooling effectiveness, C thermal capacitance. The fitted model "
                f"tracks the noisy readings to {calibration.rmse_c:.3f} °C RMSE over the evening "
                f"({calibration.ac_on_min} AC-on minutes), which is the 0.2 °C sensor noise itself. "
                f"Temperature data pins down only R·C and eta/C, so C keeps its default. Turn on \"Use calibrated room model\" in the sidebar to run both evenings "
                f"on the fitted model. In use now: {room_model_label}."
            )

    with st.expander("Why this is a lower bound on achievable peak"):
        st.markdown("The benchmark relaxes rules the engine enforces:")
        st.markdown("\n".join(f"- {r}" for r in opt.relaxations))
    st.caption(
        f"No cost or emissions claims: a lower peak does not by itself reduce energy or "
        f"emissions. Solved in {opt.solve_time_s:.2f} s (SciPy HiGHS, 1-minute steps)."
    )

# Decision log + device status.
left, right = st.columns([3, 2])
with left:
    st.subheader("Decision log (coordinated)")
    st.caption("Plain-language reason for each control change. SIMULATED.")
    log_rows = [d.as_row() for d in co.decision_log]
    n_cycling = sum(1 for r in log_rows if _is_ac_cycling(r))
    show_cycling = False
    if n_cycling:
        show_cycling = st.toggle(
            f"Show AC on/off cycling ({n_cycling} entries)", value=False,
            help="The AC switches on and off to hold the room near the comfort limit. "
                 "Hidden by default so the EV and water-heater decisions stand out.",
        )
    shown = log_rows if show_cycling else [r for r in log_rows if not _is_ac_cycling(r)]
    if shown:
        st.dataframe(pd.DataFrame(shown), height=300, use_container_width=True, hide_index=True)
    elif log_rows:
        st.write("Only AC on/off cycling was logged. Use the toggle above to show it.")
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
