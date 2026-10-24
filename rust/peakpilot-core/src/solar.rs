//! On-site rooftop PV with a perturb-and-observe MPPT inverter (pure standard library).
//!
//! Port of the PV section of `peakpilot/engine.py`. The arithmetic follows the Python source
//! operation for operation, and Python's two-argument `min` / `max` and built-in `sum()` are
//! reproduced exactly, so both engines produce bit-identical PV series. All values SIMULATED.

use crate::engine::py_sum;
use crate::model::WINDOW_MINUTES;

/// Simulated rooftop PV array and inverter (illustrative, not a real installation).
///
/// One equivalent string on the ideal single-diode curve `I(V) = Isc * (1 - exp((V - Voc) / a))`.
/// `Isc` scales with irradiance; `Isc`, `Voc` and the diode voltage `a` shift with cell
/// temperature. About 5.8 kW DC at standard test conditions (1000 W/m², 25 °C cells).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PVArray {
    /// Short-circuit current at STC, A.
    pub isc_stc_a: f64,
    /// Open-circuit voltage at STC, V.
    pub voc_stc_v: f64,
    /// Diode voltage n·Ns·kT/q at 25 °C, V.
    pub a_stc_v: f64,
    /// Isc temperature coefficient, per °C.
    pub alpha_isc: f64,
    /// Voc temperature coefficient, per °C.
    pub beta_voc: f64,
    /// Nominal operating cell temperature, °C.
    pub noct_c: f64,
    /// Inverter AC rating, kW.
    pub inverter_kw: f64,
    pub inverter_eff: f64,
    /// Perturbation size, V.
    pub mppt_step_v: f64,
    /// Perturbations per one-minute step.
    pub mppt_iterations: u32,
}

impl Default for PVArray {
    /// Same defaults as the Python `PVArray`.
    fn default() -> Self {
        PVArray {
            isc_stc_a: 18.0,
            voc_stc_v: 400.0,
            a_stc_v: 20.0,
            alpha_isc: 0.0005,
            beta_voc: -0.003,
            noct_c: 45.0,
            inverter_kw: 6.0,
            inverter_eff: 0.96,
            mppt_step_v: 2.0,
            mppt_iterations: 20,
        }
    }
}

/// On-site solar input: plane-of-array irradiance in W/m², one value per minute.
#[derive(Debug, Clone, PartialEq)]
pub struct Solar {
    pub irradiance_w_m2: Vec<f64>,
    pub array: PVArray,
}

/// PV output for one scenario (SIMULATED). Both runs use this same series.
///
/// `pv_kw` is what the MPPT inverter delivers; `mpp_kw` is the AC output at the true maximum
/// power point. `tracking_efficiency` is tracked ÷ true-MPP DC energy over sunlit minutes.
#[derive(Debug, Clone, PartialEq)]
pub struct SolarResult {
    pub irradiance_w_m2: Vec<f64>,
    pub cell_c: Vec<f64>,
    pub mppt_v: Vec<f64>,
    pub pv_kw: Vec<f64>,
    pub mpp_kw: Vec<f64>,
    pub pv_kwh: f64,
    pub tracking_efficiency: f64,
}

/// Python's `min(a, b)`: returns `a` unless `b < a`.
fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}

/// Python's `max(a, b)`: returns `a` unless `b > a`.
fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}

/// `(isc_a, voc_v, diode_v)` for the array at this irradiance and cell temperature.
pub fn pv_curve(g_w_m2: f64, cell_c: f64, a: &PVArray) -> (f64, f64, f64) {
    let diode_v = a.a_stc_v * (cell_c + 273.15) / 298.15;
    let isc = a.isc_stc_a * (g_w_m2 / 1000.0) * (1.0 + a.alpha_isc * (cell_c - 25.0));
    let voc = a.voc_stc_v * (1.0 + a.beta_voc * (cell_c - 25.0)) + diode_v * (g_w_m2 / 1000.0).ln();
    (isc, py_max(0.0, voc), diode_v)
}

/// DC power in W at array voltage `v` on the ideal single-diode curve.
pub fn pv_power_w(v: f64, isc: f64, voc: f64, diode_v: f64) -> f64 {
    if v <= 0.0 || v >= voc {
        return 0.0;
    }
    v * isc * (1.0 - ((v - voc) / diode_v).exp())
}

/// Maximum DC power in W, by golden-section search (P(V) is unimodal on [0, Voc]).
pub fn true_mpp_w(isc: f64, voc: f64, diode_v: f64) -> f64 {
    let (mut lo, mut hi) = (0.0_f64, voc);
    let inv_phi = (5.0_f64.sqrt() - 1.0) / 2.0;
    for _ in 0..80 {
        let x1 = hi - inv_phi * (hi - lo);
        let x2 = lo + inv_phi * (hi - lo);
        if pv_power_w(x1, isc, voc, diode_v) < pv_power_w(x2, isc, voc, diode_v) {
            lo = x1;
        } else {
            hi = x2;
        }
    }
    pv_power_w((lo + hi) / 2.0, isc, voc, diode_v)
}

/// Run the MPPT inverter over the window against `outdoor_c` (deterministic).
pub fn simulate_solar(solar: &Solar, outdoor_c: &[f64]) -> SolarResult {
    let a = &solar.array;
    let mut v = 0.8 * a.voc_stc_v; // tracker's starting operating voltage
    let mut direction = 1.0_f64;
    let mut cells = Vec::with_capacity(WINDOW_MINUTES);
    let mut volts = Vec::with_capacity(WINDOW_MINUTES);
    let mut pv_kw = Vec::with_capacity(WINDOW_MINUTES);
    let mut mpp_kw = Vec::with_capacity(WINDOW_MINUTES);
    let (mut tracked_dc, mut ideal_dc) = (0.0_f64, 0.0_f64);
    let cap_w = a.inverter_kw * 1000.0;
    for (&g, &outdoor) in solar
        .irradiance_w_m2
        .iter()
        .zip(outdoor_c)
        .take(WINDOW_MINUTES)
    {
        let cell = outdoor + (a.noct_c - 20.0) / 800.0 * py_max(0.0, g);
        cells.push(cell);
        if g <= 0.0 {
            // Night: no output; the tracker keeps its voltage for the next sunrise.
            volts.push(v);
            pv_kw.push(0.0);
            mpp_kw.push(0.0);
            continue;
        }
        let (isc, voc, diode_v) = pv_curve(g, cell, a);
        v = py_min(py_max(v, 0.0), voc);
        let mut p = pv_power_w(v, isc, voc, diode_v);
        for _ in 0..a.mppt_iterations {
            let v_next = py_min(py_max(v + direction * a.mppt_step_v, 0.0), voc);
            let p_next = pv_power_w(v_next, isc, voc, diode_v);
            if p_next < p {
                direction = -direction;
            }
            v = v_next;
            p = p_next;
        }
        let ideal = true_mpp_w(isc, voc, diode_v);
        tracked_dc += p;
        ideal_dc += ideal;
        volts.push(v);
        pv_kw.push(py_min(cap_w, p * a.inverter_eff) / 1000.0);
        mpp_kw.push(py_min(cap_w, ideal * a.inverter_eff) / 1000.0);
    }
    let pv_kwh = py_sum(pv_kw.iter().copied()) / 60.0;
    SolarResult {
        irradiance_w_m2: solar.irradiance_w_m2.clone(),
        cell_c: cells,
        mppt_v: volts,
        pv_kw,
        mpp_kw,
        pv_kwh,
        tracking_efficiency: if ideal_dc > 0.0 {
            tracked_dc / ideal_dc
        } else {
            1.0
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn true_mpp_beats_every_other_voltage() {
        let (isc, voc, a) = pv_curve(800.0, 40.0, &PVArray::default());
        let best = true_mpp_w(isc, voc, a);
        for i in 1..400 {
            assert!(pv_power_w(voc * i as f64 / 400.0, isc, voc, a) <= best + 1e-6);
        }
    }

    #[test]
    fn no_power_outside_zero_to_voc() {
        let (isc, voc, a) = pv_curve(600.0, 30.0, &PVArray::default());
        assert_eq!(pv_power_w(0.0, isc, voc, a), 0.0);
        assert_eq!(pv_power_w(voc, isc, voc, a), 0.0);
        assert_eq!(pv_power_w(voc + 1.0, isc, voc, a), 0.0);
    }
}
