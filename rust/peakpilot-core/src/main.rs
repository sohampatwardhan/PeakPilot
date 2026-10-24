//! `peakpilot` command-line interface.
//!
//! ```text
//! peakpilot list
//! peakpilot run --scenario <slug> [--table] [--pretty] [overrides]
//! ```
//!
//! `run` prints the comparison as JSON (the same shape as the Python `to_json_dict()`), or a
//! human-readable summary with `--table`. Overrides adjust a named scenario's knobs while
//! keeping the rest of it (outdoor temperature, offline window). Exit code 2 = bad usage.

use std::process::ExitCode;

use peakpilot_core::{engine, json, scenarios, CompareResult, WINDOW_MINUTES};

const USAGE: &str = "\
Usage:
  peakpilot list
  peakpilot run --scenario <slug> [--table] [--pretty]
                [--limit KW] [--ev-kwh KWH] [--ev-deadline-min MIN]
                [--wh-kwh KWH] [--wh-deadline-min MIN]

Deadlines are minutes after 16:00 (0..=960). All device data is SIMULATED.";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match dispatch(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("error: {message}\n\n{USAGE}");
            ExitCode::from(2)
        }
    }
}

fn dispatch(args: &[String]) -> Result<(), String> {
    match args.first().map(String::as_str) {
        Some("list") => {
            for s in scenarios::all() {
                println!("{}\t{}", s.slug, s.display_name);
            }
            Ok(())
        }
        Some("run") => cmd_run(&args[1..]),
        Some("help" | "-h" | "--help") => {
            println!("{USAGE}");
            Ok(())
        }
        Some(other) => Err(format!("unknown command '{other}'")),
        None => Err("missing command".to_string()),
    }
}

fn take_value<'a>(
    it: &mut impl Iterator<Item = &'a String>,
    flag: &str,
) -> Result<&'a str, String> {
    it.next()
        .map(String::as_str)
        .ok_or_else(|| format!("{flag} needs a value"))
}

fn parse_f64(value: &str, flag: &str, min: f64) -> Result<f64, String> {
    let v: f64 = value
        .parse()
        .map_err(|_| format!("{flag}: '{value}' is not a number"))?;
    if !v.is_finite() || v < min {
        return Err(format!("{flag}: must be a finite number >= {min}"));
    }
    Ok(v)
}

fn parse_minutes(value: &str, flag: &str) -> Result<u32, String> {
    let v: u32 = value
        .parse()
        .map_err(|_| format!("{flag}: '{value}' is not a whole number of minutes"))?;
    if v as usize > WINDOW_MINUTES {
        return Err(format!("{flag}: must be between 0 and {WINDOW_MINUTES}"));
    }
    Ok(v)
}

fn cmd_run(args: &[String]) -> Result<(), String> {
    let mut slug: Option<&str> = None;
    let mut table = false;
    let mut pretty = false;
    let mut limit = None;
    let mut ev_kwh = None;
    let mut ev_deadline = None;
    let mut wh_kwh = None;
    let mut wh_deadline = None;

    let mut it = args.iter();
    while let Some(arg) = it.next() {
        match arg.as_str() {
            "--scenario" => slug = Some(take_value(&mut it, arg)?),
            "--table" => table = true,
            "--pretty" => pretty = true,
            "--limit" => {
                limit = Some(parse_f64(
                    take_value(&mut it, arg)?,
                    arg,
                    f64::MIN_POSITIVE,
                )?)
            }
            "--ev-kwh" => ev_kwh = Some(parse_f64(take_value(&mut it, arg)?, arg, 0.0)?),
            "--ev-deadline-min" => {
                ev_deadline = Some(parse_minutes(take_value(&mut it, arg)?, arg)?)
            }
            "--wh-kwh" => wh_kwh = Some(parse_f64(take_value(&mut it, arg)?, arg, 0.0)?),
            "--wh-deadline-min" => {
                wh_deadline = Some(parse_minutes(take_value(&mut it, arg)?, arg)?)
            }
            other => return Err(format!("unknown option '{other}'")),
        }
    }

    let slug = slug.ok_or("--scenario is required (see `peakpilot list`)")?;
    let mut params =
        scenarios::params_for(slug).ok_or_else(|| format!("unknown scenario '{slug}'"))?;
    if let Some(v) = limit {
        params.power_limit_kw = v;
    }
    if let Some(v) = ev_kwh {
        params.ev_kwh = v;
    }
    if let Some(v) = ev_deadline {
        params.ev_deadline_min = v;
    }
    if let Some(v) = wh_kwh {
        params.wh_kwh = v;
    }
    if let Some(v) = wh_deadline {
        params.wh_deadline_min = v;
    }

    let result = engine::compare(&scenarios::build(&params));
    if table {
        print_table(&result);
    } else {
        let out = json::to_json_string(&result, pretty).map_err(|e| e.to_string())?;
        println!("{out}");
    }
    Ok(())
}

fn print_table(c: &CompareResult) {
    let (b, p) = (&c.baseline, &c.coordinated);
    let met = |all: bool| if all { "all met" } else { "UNMET" };
    println!(
        "{} — power limit {:.1} kW (SIMULATED)",
        c.scenario_name, c.power_limit_kw
    );
    println!("{:<26}{:>16}{:>16}", "", "Uncoordinated", "PeakPilot");
    println!(
        "{:<26}{:>16.2}{:>16.2}",
        "Peak demand (kW)", b.peak_kw, p.peak_kw
    );
    println!(
        "{:<26}{:>16.2}{:>16.2}",
        "Energy delivered (kWh)", b.total_kwh, p.total_kwh
    );
    println!(
        "{:<26}{:>16}{:>16}",
        "Minutes over limit", b.minutes_over_limit, p.minutes_over_limit
    );
    println!(
        "{:<26}{:>16}{:>16}",
        "Minutes above comfort", b.temp_violation_min, p.temp_violation_min
    );
    println!(
        "{:<26}{:>16}{:>16}",
        "Deadlines",
        met(b.all_tasks_met()),
        met(p.all_tasks_met())
    );
    println!("Peak reduction: {:.1}%", c.peak_reduction_pct());
    if let Some(s) = &c.solar {
        println!(
            "Rooftop PV (SIMULATED): {:.1} kWh, MPPT tracking efficiency {:.2}%; demand is net grid import",
            s.pv_kwh,
            100.0 * s.tracking_efficiency
        );
    }
}
