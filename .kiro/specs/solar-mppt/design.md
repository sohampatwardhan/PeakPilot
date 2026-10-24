# On-site solar with MPPT — Design

Issue: [#33](https://github.com/sohampatwardhan/PeakPilot/issues/33).

## Data model (`engine.py`)

- `PVArray` (frozen): one equivalent string. `isc_stc_a=18`, `voc_stc_v=400`, diode voltage
  `a_stc_v=20` (n·Ns·kT/q at 25 °C), `alpha_isc=+0.0005/°C`, `beta_voc=−0.003/°C`, `noct_c=45`,
  `inverter_kw=6`, `inverter_eff=0.96`, `mppt_step_v=2`, `mppt_iterations=20`. About 5.8 kW DC at STC.
- `Solar` (frozen): `irradiance_w_m2` (960 values, plane of array) and `array: PVArray`.
- `Scenario.solar: Solar | None = None`.
- `SolarResult` (frozen): `irradiance_w_m2`, `cell_c`, `mppt_v`, `pv_kw`, `mpp_kw` (tuples), `pv_kwh`,
  `tracking_efficiency`. `CompareResult.solar` carries it; `to_json_dict()` adds a `"solar"` key only
  when it is present (R2.3).

## Physics

```
Tc   = Tamb + (NOCT − 20)/800 · G
a    = a_stc · (Tc + 273.15)/298.15
Isc  = Isc_stc · G/1000 · (1 + α(Tc − 25))
Voc  = Voc_stc · (1 + β(Tc − 25)) + a · ln(G/1000)
I(V) = Isc · (1 − exp((V − Voc)/a)),   P(V) = V · I(V) on [0, Voc]
```

P(V) is unimodal on [0, Voc], so the true MPP is found by golden-section search (80 iterations).

## MPPT (perturb and observe)

Per minute, from the previous operating voltage clamped to [0, Voc]: step `mppt_step_v` in the
current direction; if power fell, reverse direction. Repeat `mppt_iterations` times (a real tracker
runs many times per second; 20 per minute is enough to settle). AC output =
`min(inverter_kw, P_dc · η)`. Night minutes output 0 and keep the voltage.

## Engine integration

`pv_kw_series(scenario)` returns the PV tuple (all zeros without solar; cached on the inputs).
Baseline and coordinated totals subtract `pv[m]`; coordinated `committed` starts at
`base[m] − pv[m]`, and the water-heater forecast uses `max(base[t] − pv[t])`. Subtracting 0.0 leaves
floats bit-identical, so no-solar results are unchanged. Net import can go negative (export).

## Other modules

- `scenarios.py`: `clear_sky_irradiance()` (Boston summer, sunrise 05:15, sunset 20:20, 950 W/m² peak),
  `sunny_evening()` = tight 11 kW case + `Solar`.
- `optimal.py`: base load in the peak rows and totals becomes `base − pv`.
- `app.py`: PV trace on the demand chart, and a "Rooftop solar (SIMULATED)" row with PV kWh and MPPT
  tracking efficiency.

## Test plan (`tests/test_solar.py`)

Zero at night; ≤ true MPP and inverter rating; tracking efficiency ≥ 0.98; deterministic; both runs
share PV; `total_kw = base + devices − pv`; sunny scenario meets all deadlines with zero minutes over
the limit; no-solar JSON has no `"solar"` key; LP total uses net load.
