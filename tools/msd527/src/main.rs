//! msd527 -- MinaCalc v527 as a stdin/stdout JSON filter.
//!
//! Same contract as the binary this replaces, so the Python side stays a single
//! subprocess call:
//!
//!   stdin : [{"notes": 9, "time": 1.234}, ...]      time in seconds, already rated
//!   stdout: {"overall": 27.2, "stream": ..., "version": 527}
//!
//! Usage: msd527 [goal] [ssr|msd]      defaults to 1.0 ssr
//!
//! `ssr` is the score-relative rating Etterna displays; `msd` is the raw
//! uncapped number. The goal is the accuracy the rating is quoted at.
//!
//! The input timestamps are already divided by the music rate upstream, so the
//! rate passed to the calculator is 1.0 by design: applying it twice would
//! shorten the chart a second time.

use std::io::{self, Read, Write};

use minacalc_rs::{Calc, CalcMode, Note};
use serde::Deserialize;

#[derive(Deserialize)]
struct Row {
    notes: u32,
    time: f64,
}

fn main() {
    let goal: f32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(1.0);
    let mode = match std::env::args().nth(2).as_deref() {
        Some("msd") => CalcMode::Msd,
        _ => CalcMode::Ssr,
    };

    let mut raw = String::new();
    if io::stdin().read_to_string(&mut raw).is_err() {
        eprintln!("msd527: cannot read stdin");
        std::process::exit(2);
    }

    let rows: Vec<Row> = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("msd527: bad input json: {e}");
            std::process::exit(2);
        }
    };
    if rows.is_empty() {
        eprintln!("msd527: no notes provided");
        std::process::exit(2);
    }

    let note_vector: Vec<Note> = rows
        .iter()
        .map(|r| Note {
            notes: r.notes,
            row_time: r.time as f32,
        })
        .collect();

    let calc = match Calc::new() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("msd527: cannot create calculator: {e:?}");
            std::process::exit(3);
        }
    };

    let scores = match calc.calc_at_rate(&note_vector, 1.0, goal, 4u32, mode) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("msd527: calculation failed: {e:?}");
            std::process::exit(3);
        }
    };

    let out = serde_json::json!({
        "overall": scores.overall,
        "stream": scores.stream,
        "jumpstream": scores.jumpstream,
        "handstream": scores.handstream,
        "stamina": scores.stamina,
        "jackspeed": scores.jackspeed,
        "chordjack": scores.chordjack,
        "technical": scores.technical,
        "version": Calc::version(),
    });

    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = writeln!(lock, "{out}");
}
